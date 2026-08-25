from typing import Literal

from pydantic import BaseModel

from app.schemas.performance import ValidationFinding


class TableInspection(BaseModel):
    source_name: str
    header_row: int
    row_count: int
    columns: list[str]


class FieldMapping(BaseModel):
    source_name: str
    entity: str | None
    mapped_fields: list[str]
    missing_fields: list[str]


class ImportIssue(BaseModel):
    code: str
    message: str
    source_name: str | None = None
    row_number: int | None = None


class AnalyzeUploadResponse(BaseModel):
    file_name: str
    file_type: Literal["csv", "xlsx"]
    byte_size: int
    tables: list[TableInspection]
    mappings: list[FieldMapping]
    import_issues: list[ImportIssue]
    validation_findings: list[ValidationFinding]
    ready_to_score: bool
