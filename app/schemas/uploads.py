from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

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


class DataCatalog(BaseModel):
    tables: list[CatalogTable]


class UploadCatalog(DataCatalog):
    file_name: str
    file_type: Literal["csv", "xlsx"]
    byte_size: int


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


type TableRole = Literal[
    "productivity",
    "compliance",
    "quality",
    "shared",
    "irrelevant",
    "unsupported",
]
type CalculatorName = Literal[
    "calculate_productivity",
    "calculate_attendance_compliance",
    "calculate_submission_compliance",
    "calculate_leave_compliance",
    "calculate_quality",
    "load_employees",
    "load_performance_targets",
]


class CalculatorInvocation(BaseModel):
    calculator: CalculatorName
    field_bindings: dict[str, str]


class TableClassification(BaseModel):
    source_name: str
    kpi_family: TableRole
    calculator_invocations: list[CalculatorInvocation]
    confidence: Literal["low", "medium", "high"]
    rationale: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_unique_calculators(self) -> Self:
        calculators = [
            invocation.calculator for invocation in self.calculator_invocations
        ]
        if len(calculators) != len(set(calculators)):
            raise ValueError("A table cannot invoke the same calculator more than once.")
        return self


class AgentTableClassification(BaseModel):
    source_name: str
    kpi_family: TableRole
    calculator_invocations: list[CalculatorInvocation]
    confidence: Literal["low", "medium", "high"]

    @model_validator(mode="after")
    def validate_unique_calculators(self) -> Self:
        calculators = [
            invocation.calculator for invocation in self.calculator_invocations
        ]
        if len(calculators) != len(set(calculators)):
            raise ValueError("A table cannot invoke the same calculator more than once.")
        return self


class AgentCalculationPlan(BaseModel):
    table_classifications: list[AgentTableClassification]

    @model_validator(mode="after")
    def validate_unique_sources(self) -> Self:
        sources = [item.source_name for item in self.table_classifications]
        if len(sources) != len(set(sources)):
            raise ValueError("Each source table must have exactly one classification.")
        return self


class ClassificationValidation(BaseModel):
    source_name: str
    kpi_family: str
    valid: bool
    unknown_source_columns: list[str]
    duplicate_source_columns: list[str]
    missing_required_fields: list[str]
    invalid_calculators: list[str]
    message: str


class CalculationPlan(BaseModel):
    selected_tables: list[str]
    table_classifications: list[TableClassification]

    @model_validator(mode="after")
    def validate_selected_tables(self) -> Self:
        classified_sources = [item.source_name for item in self.table_classifications]
        if len(classified_sources) != len(set(classified_sources)):
            raise ValueError("Each source table must have exactly one classification.")
        expected = {
            item.source_name
            for item in self.table_classifications
            if item.kpi_family not in {"irrelevant", "unsupported"}
        }
        if set(self.selected_tables) != expected or len(self.selected_tables) != len(expected):
            raise ValueError(
                "selected_tables must contain each relevant classified table exactly once."
            )
        return self


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


class AnalysisResponse(BaseModel):
    analysis_id: str
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
    table_classifications: list[TableClassification]
    limitations: list[str]
    model: str
    total_tokens: int
    model_requests: int
    mapping_cache_hit: bool


class AnalyzeUploadResponse(AnalysisResponse):
    file_name: str
    file_type: Literal["csv", "xlsx"]
    byte_size: int
