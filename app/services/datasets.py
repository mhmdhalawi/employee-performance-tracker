from datetime import date, datetime
from types import UnionType
from typing import get_args

from pydantic import BaseModel, ValidationError

from app.schemas.performance import (
    AttendanceRecord,
    Employee,
    KpiTarget,
    LeaveRequest,
    PerformanceDataset,
    Project,
    QualityReview,
    Report,
)
from app.schemas.uploads import ImportIssue, MappingProposal, UploadCatalog
from app.services import catalog as catalog_service

_CANONICAL_COLLECTIONS: dict[str, tuple[type[BaseModel], str]] = {
    "employees": (Employee, "employees"),
    "kpi_targets": (KpiTarget, "kpi_targets"),
    "projects": (Project, "projects"),
    "attendance": (AttendanceRecord, "attendance"),
    "reports": (Report, "reports"),
    "leave_requests": (LeaveRequest, "leave_requests"),
    "quality_reviews": (QualityReview, "quality_reviews"),
}


def build_performance_dataset(
    upload_catalog: UploadCatalog,
    proposals: list[MappingProposal],
) -> tuple[PerformanceDataset, list[ImportIssue]]:
    """Apply validated agent mappings and report unusable source rows."""
    collections: dict[str, list[BaseModel]] = {
        collection_name: []
        for _, collection_name in _CANONICAL_COLLECTIONS.values()
    }
    issues: list[ImportIssue] = []
    mapped_fields: dict[str, set[str]] = {}

    for proposal in proposals:
        target = _CANONICAL_COLLECTIONS.get(proposal.canonical_entity)
        if target is None:
            issues.append(
                ImportIssue(
                    code="unknown_canonical_entity",
                    message=f"Unknown canonical entity: {proposal.canonical_entity}.",
                    source_name=proposal.source_name,
                )
            )
            continue

        validation = catalog_service.validate_mapping(
            upload_catalog,
            proposal.source_name,
            proposal.canonical_entity,
            proposal.field_mappings,
        )
        if not validation.valid:
            issues.append(
                ImportIssue(
                    code="invalid_mapping",
                    message=validation.message,
                    source_name=proposal.source_name,
                )
            )
            continue

        model, collection_name = target
        mapped_fields.setdefault(collection_name, set()).update(
            proposal.field_mappings
        )
        table = next(
            table
            for table in upload_catalog.tables
            if table.source_name == proposal.source_name
        )
        for row in table.rows:
            source_row = row.get("_source_row")
            row_number = (
                source_row
                if isinstance(source_row, int) and not isinstance(source_row, bool)
                else None
            )
            mapped_row = {
                canonical_field: _normalize_value(
                    model,
                    canonical_field,
                    row.get(source_column),
                )
                for canonical_field, source_column in proposal.field_mappings.items()
                if row.get(source_column) is not None
            }
            try:
                collections[collection_name].append(model.model_validate(mapped_row))
            except ValidationError as exc:
                issues.append(
                    ImportIssue(
                        code="invalid_row",
                        message=str(exc),
                        source_name=proposal.source_name,
                        row_number=row_number,
                    )
                )

    dataset_data: dict[str, object] = {
        **collections,
        "mapped_fields": mapped_fields,
    }
    return PerformanceDataset.model_validate(dataset_data), issues


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
