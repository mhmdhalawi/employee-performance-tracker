from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.performance import (
    DatasetOverview,
    EmployeeKpiScores,
    KpiTrendPoint,
    PerformanceAlert,
    ValidationFinding,
    ValidationSummary,
)

type CellValue = str | int | float | bool | None


class TableInspection(BaseModel):
    source_name: str
    header_row: int | None
    row_count: int
    columns: list[str]


class CatalogTable(TableInspection):
    rows: list[dict[str, CellValue]]


class UploadCatalog(BaseModel):
    file_name: str
    file_type: Literal["csv", "xlsx"]
    byte_size: int
    tables: list[CatalogTable]


class ColumnDescription(BaseModel):
    name: str
    inferred_type: str
    missing_count: int
    unique_count: int


class TableDescription(BaseModel):
    source_name: str
    header_row: int | None
    row_count: int
    columns: list[ColumnDescription]
    sample_rows: list[dict[str, CellValue]]


class TableProfile(BaseModel):
    source_name: str
    blank_columns: list[str]
    duplicate_row_count: int
    likely_id_columns: list[str]
    date_like_columns: list[str]
    numeric_columns: list[str]


class TableAnalysis(BaseModel):
    description: TableDescription
    profile: TableProfile


class RowPage(BaseModel):
    source_name: str
    columns: list[str]
    rows: list[dict[str, CellValue]]
    total_matching_rows: int
    truncated: bool


class DistinctValues(BaseModel):
    source_name: str
    column: str
    values: list[CellValue]
    total_distinct_values: int
    truncated: bool


class MappingProposal(BaseModel):
    source_name: str
    canonical_entity: str
    field_mappings: dict[str, str]
    confidence: Literal["low", "medium", "high"]


class MappingValidation(BaseModel):
    source_name: str
    canonical_entity: str
    valid: bool
    unknown_source_columns: list[str]
    duplicate_source_columns: list[str]
    missing_required_fields: list[str]
    message: str


class UploadAnalysis(BaseModel):
    selected_tables: list[str]
    mapping_proposals: list[MappingProposal]


class ImportIssue(BaseModel):
    code: str
    message: str
    source_name: str | None = None
    row_number: int | None = None


class AnalysisSummary(BaseModel):
    total_employee_count: int = Field(ge=0)
    scored_employee_count: int = Field(ge=0)
    insufficient_data_count: int = Field(ge=0)
    insufficient_data_employee_ids: list[str]
    performance_tier_counts: dict[str, int]
    narrative: str


class AnalysisFilters(BaseModel):
    employee_id: str | None = None
    team: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class AIInsightStatement(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    record_ids: list[str] = Field(min_length=1, max_length=5)


class EmployeeAIInsight(BaseModel):
    employee_id: str = Field(min_length=1)
    explanation: AIInsightStatement
    recommendations: list[AIInsightStatement] = Field(min_length=1, max_length=2)


class AIInsightRequest(BaseModel):
    analysis_id: str = Field(min_length=1)
    employee_id: str = Field(min_length=1)


class AIInsightResponse(BaseModel):
    insight: EmployeeAIInsight
    model: str
    total_tokens: int = Field(ge=0)
    model_requests: int = Field(ge=0)


class AnalyzeUploadResponse(BaseModel):
    analysis_id: str
    file_name: str
    file_type: Literal["csv", "xlsx"]
    byte_size: int
    results: list[EmployeeKpiScores]
    summary: AnalysisSummary
    dataset_overview: DatasetOverview
    applied_filters: AnalysisFilters
    available_teams: list[str]
    trends: list[KpiTrendPoint]
    alerts: list[PerformanceAlert]
    import_issues: list[ImportIssue]
    validation_summary: ValidationSummary
    global_validation_findings: list[ValidationFinding]
    selected_tables: list[str]
    limitations: list[str]
    model: str
    total_tokens: int
    model_requests: int
    mapping_cache_hit: bool
