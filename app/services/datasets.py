from datetime import date, datetime
from types import UnionType
from typing import get_args

from pydantic import BaseModel, ValidationError

from app.schemas.calculators import CALCULATOR_BY_NAME, CALCULATORS
from app.schemas.performance import PerformanceEvidenceDataset
from app.schemas.uploads import DataCatalog, ImportIssue, TableClassification
from app.services import catalog as catalog_service


def build_performance_dataset(
    upload_catalog: DataCatalog,
    classifications: list[TableClassification],
) -> tuple[PerformanceEvidenceDataset, list[ImportIssue]]:
    """Apply a validated classification plan and report unusable source rows."""
    collections: dict[str, list[BaseModel]] = {
        spec.collection_name: [] for spec in CALCULATORS
    }
    issues: list[ImportIssue] = []
    mapped_fields: dict[str, set[str]] = {}

    for classification in classifications:
        if classification.kpi_family == "irrelevant":
            continue
        validation = catalog_service.validate_classification(upload_catalog, classification)
        if not validation.valid:
            issues.append(
                ImportIssue(
                    code="invalid_classification",
                    message=validation.message,
                    source_name=classification.source_name,
                )
            )
            continue

        table = next(
            table
            for table in upload_catalog.tables
            if table.source_name == classification.source_name
        )
        for invocation in classification.calculator_invocations:
            spec = CALCULATOR_BY_NAME.get(invocation.calculator)
            if spec is None:
                continue
            model = spec.model
            mapped_fields.setdefault(spec.collection_name, set()).update(
                invocation.field_bindings
            )
            for row in table.rows:
                source_row = row.get("_source_row")
                row_number = (
                    source_row
                    if isinstance(source_row, int) and not isinstance(source_row, bool)
                    else None
                )
                mapped_row = {
                    calculator_field: _normalize_value(
                        model,
                        calculator_field,
                        row.get(source_column),
                    )
                    for calculator_field, source_column in invocation.field_bindings.items()
                    if row.get(source_column) is not None
                }
                try:
                    collections[spec.collection_name].append(
                        model.model_validate(mapped_row)
                    )
                except ValidationError as exc:
                    issues.append(
                        ImportIssue(
                            code="invalid_row",
                            message=str(exc),
                            source_name=classification.source_name,
                            row_number=row_number,
                        )
                    )

    dataset_data: dict[str, object] = {
        **collections,
        "mapped_fields": mapped_fields,
    }
    return PerformanceEvidenceDataset.model_validate(dataset_data), issues


def _normalize_value(
    model: type[BaseModel],
    field_name: str,
    value: object,
) -> object:
    field = model.model_fields.get(field_name)
    if field is None or not isinstance(value, str):
        return value

    annotation = field.annotation
    date_field = annotation is date or (
        isinstance(annotation, UnionType) and date in get_args(annotation)
    )
    if not date_field or "T" not in value:
        return value

    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return value
