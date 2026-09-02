from datetime import date, datetime
from types import UnionType
from typing import get_args

from pydantic import BaseModel, ValidationError

from app.schemas.performance import (
    AttendanceComplianceEvidence,
    Employee,
    LeaveComplianceEvidence,
    PerformanceEvidenceDataset,
    PerformanceTarget,
    QualityEvidence,
    SubmissionComplianceEvidence,
    WorkOutputEvidence,
)
from app.schemas.uploads import DataCatalog, ImportIssue, TableClassification
from app.services import catalog as catalog_service

_CALCULATOR_INPUTS: dict[str, tuple[type[BaseModel], str]] = {
    "load_employees": (Employee, "employees"),
    "load_performance_targets": (PerformanceTarget, "performance_targets"),
    "calculate_productivity": (WorkOutputEvidence, "work_outputs"),
    "calculate_attendance_compliance": (AttendanceComplianceEvidence, "attendance_events"),
    "calculate_submission_compliance": (SubmissionComplianceEvidence, "submission_events"),
    "calculate_leave_compliance": (LeaveComplianceEvidence, "leave_events"),
    "calculate_quality": (QualityEvidence, "quality_events"),
}


def build_performance_dataset(
    upload_catalog: DataCatalog,
    classifications: list[TableClassification],
) -> tuple[PerformanceEvidenceDataset, list[ImportIssue]]:
    """Apply a validated classification plan and report unusable source rows."""
    collections: dict[str, list[BaseModel]] = {
        collection_name: []
        for _, collection_name in _CALCULATOR_INPUTS.values()
    }
    issues: list[ImportIssue] = []
    mapped_fields: dict[str, set[str]] = {}

    for classification in classifications:
        if classification.kpi_family in {"irrelevant", "unsupported"}:
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
            target = _CALCULATOR_INPUTS.get(invocation.calculator)
            if target is None:
                continue
            model, collection_name = target
            mapped_fields.setdefault(collection_name, set()).update(
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
                    collections[collection_name].append(model.model_validate(mapped_row))
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
