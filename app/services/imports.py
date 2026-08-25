import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath
from typing import Any

import pandas as pd
from pydantic import BaseModel, ValidationError

from app.core.errors import AppError
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
from app.schemas.uploads import (
    AnalyzeUploadResponse,
    FieldMapping,
    ImportIssue,
    TableInspection,
)
from app.services.performance import validate_dataset
from app.services.uploads import accept_upload


class UnparseableFileError(AppError):
    """The upload cannot be read as the declared CSV or Excel format."""

    status_code = 422
    code = "unparseable_file"


@dataclass(frozen=True)
class EntitySpec[ModelT: BaseModel]:
    name: str
    model: type[ModelT]
    sheet_names: set[str]


_ENTITY_SPECS: tuple[EntitySpec[Any], ...] = (
    EntitySpec("employees", Employee, {"employees", "employee"}),
    EntitySpec("kpi_targets", KpiTarget, {"kpitargets", "targets"}),
    EntitySpec("projects", Project, {"projects", "project"}),
    EntitySpec("attendance", AttendanceRecord, {"attendance"}),
    EntitySpec("reports", Report, {"reports", "report"}),
    EntitySpec("leave_requests", LeaveRequest, {"leaverequests", "leave"}),
    EntitySpec("quality_reviews", QualityReview, {"qualityreviews", "quality"}),
)


def import_performance_upload(
    file_name: str | None,
    contents: bytes,
    maximum_bytes: int,
) -> AnalyzeUploadResponse:
    """Inspect, map, and validate a CSV or Excel performance-data upload."""
    receipt = accept_upload(file_name, contents, maximum_bytes)
    tables = _read_tables(receipt.file_type, contents)
    records_by_entity: dict[str, list[dict[str, object]]] = {
        spec.name: [] for spec in _ENTITY_SPECS
    }
    inspections: list[TableInspection] = []
    mappings: list[FieldMapping] = []
    import_issues: list[ImportIssue] = []

    for table in tables:
        columns = [str(column) for column in table.frame.columns]
        inspections.append(
            TableInspection(
                source_name=table.name,
                header_row=table.header_row,
                row_count=len(table.frame),
                columns=columns,
            )
        )
        spec = _find_entity(table.name, columns)
        if spec is None:
            mappings.append(FieldMapping(source_name=table.name, entity=None, mapped_fields=[], missing_fields=[]))
            continue
        field_names = set(spec.model.model_fields)
        normalized_columns = {_normalize(column): column for column in columns}
        field_to_source = {
            field: normalized_columns[_normalize(field)]
            for field in field_names
            if _normalize(field) in normalized_columns
        }
        mapped_fields = sorted(
            field for field in field_names if field in field_to_source
        )
        missing_fields = sorted(field_names - set(mapped_fields) - _optional_fields(spec.model))
        mappings.append(FieldMapping(source_name=table.name, entity=spec.name, mapped_fields=mapped_fields, missing_fields=missing_fields))
        if missing_fields:
            import_issues.append(ImportIssue(code="missing_required_columns", message=f"Cannot map {spec.name}; required columns are missing: {', '.join(missing_fields)}.", source_name=table.name))
            continue
        for row_number, row in enumerate(_records(table.frame), start=table.header_row + 2):
            try:
                canonical_row = {
                    field: row[source_column]
                    for field, source_column in field_to_source.items()
                }
                records_by_entity[spec.name].append(
                    spec.model.model_validate(canonical_row).model_dump()
                )
            except ValidationError as exc:
                import_issues.append(ImportIssue(code="invalid_row", message=exc.errors()[0]["msg"], source_name=table.name, row_number=row_number))

    dataset = PerformanceDataset(
        employees=[Employee.model_validate(record) for record in records_by_entity["employees"]],
        kpi_targets=[KpiTarget.model_validate(record) for record in records_by_entity["kpi_targets"]],
        projects=[Project.model_validate(record) for record in records_by_entity["projects"]],
        attendance=[AttendanceRecord.model_validate(record) for record in records_by_entity["attendance"]],
        reports=[Report.model_validate(record) for record in records_by_entity["reports"]],
        leave_requests=[LeaveRequest.model_validate(record) for record in records_by_entity["leave_requests"]],
        quality_reviews=[QualityReview.model_validate(record) for record in records_by_entity["quality_reviews"]],
    )
    ready_to_score = all(records_by_entity[name] for name in ("employees", "kpi_targets", "projects", "attendance", "reports", "quality_reviews"))
    return AnalyzeUploadResponse(file_name=receipt.file_name, file_type=receipt.file_type, byte_size=receipt.byte_size, tables=inspections, mappings=mappings, import_issues=import_issues, validation_findings=validate_dataset(dataset), ready_to_score=ready_to_score)


@dataclass(frozen=True)
class _RawTable:
    name: str
    header_row: int
    frame: pd.DataFrame


def _read_tables(file_type: str, contents: bytes) -> list[_RawTable]:
    try:
        if file_type == "csv":
            raw = pd.read_csv(BytesIO(contents), header=None)
            return [_table_from_raw(PurePath("upload.csv").stem, raw)]
        workbook = pd.ExcelFile(BytesIO(contents))
        return [
            _table_from_raw(str(name), pd.read_excel(workbook, sheet_name=name, header=None))
            for name in workbook.sheet_names
        ]
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise UnparseableFileError("The upload could not be read as CSV or Excel data.") from exc


def _table_from_raw(name: str, raw: pd.DataFrame) -> _RawTable:
    header_index = _find_header_row(raw)
    if header_index is None:
        return _RawTable(name=name, header_row=0, frame=pd.DataFrame())
    columns = [str(value).strip() for value in raw.iloc[header_index].tolist()]
    frame = raw.iloc[header_index + 1 :].copy()
    frame.columns = columns
    frame = frame.dropna(how="all")
    return _RawTable(name=name, header_row=header_index + 1, frame=frame)


def _find_header_row(raw: pd.DataFrame) -> int | None:
    for index in range(min(len(raw), 20)):
        values = [value for value in raw.iloc[index].tolist() if pd.notna(value) and str(value).strip()]
        if len(values) >= 2:
            return index
    return None


def _find_entity(source_name: str, columns: list[str]) -> EntitySpec[Any] | None:
    normalized_name = _normalize(source_name)
    for spec in _ENTITY_SPECS:
        if normalized_name in spec.sheet_names:
            return spec
    normalized_columns = {_normalize(column) for column in columns}
    for spec in _ENTITY_SPECS:
        required = set(spec.model.model_fields) - _optional_fields(spec.model)
        if {_normalize(field) for field in required}.issubset(normalized_columns):
            return spec
    return None


def _optional_fields(model: type[BaseModel]) -> set[str]:
    return {name for name, field in model.model_fields.items() if not field.is_required()}


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    cleaned = frame.where(pd.notna(frame), None)
    records: list[dict[str, object]] = []
    for row in cleaned.to_dict(orient="records"):
        records.append({str(key): value for key, value in row.items()})
    return records
