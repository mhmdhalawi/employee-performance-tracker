from collections.abc import Iterable, Sequence
from datetime import date

from pydantic import BaseModel

from app.schemas.performance import (
    AttendanceComplianceEvidence,
    Employee,
    LeaveComplianceEvidence,
    PerformanceTarget,
    QualityEvidence,
    SubmissionComplianceEvidence,
    WorkOutputEvidence,
)
from app.schemas.uploads import (
    CatalogTable,
    CellValue,
    ClassificationValidation,
    ColumnDescription,
    DistinctValues,
    RowPage,
    TableAnalysis,
    TableClassification,
    TableDescription,
    TableInspection,
    TableProfile,
    UploadCatalog,
)

_CALCULATOR_CONTRACTS: dict[str, tuple[type[BaseModel], str]] = {
    "load_employees": (Employee, "shared"),
    "load_performance_targets": (PerformanceTarget, "shared"),
    "calculate_productivity": (WorkOutputEvidence, "productivity"),
    "calculate_attendance_compliance": (AttendanceComplianceEvidence, "compliance"),
    "calculate_submission_compliance": (SubmissionComplianceEvidence, "compliance"),
    "calculate_leave_compliance": (LeaveComplianceEvidence, "compliance"),
    "calculate_quality": (QualityEvidence, "quality"),
}


def classification_contract() -> dict[str, object]:
    """Return approved calculators and their KPI-family input contracts."""
    return {
        "approved_calculators": {
            calculator: {
                "required_fields": [
                    name
                    for name, field in model.model_fields.items()
                    if field.is_required()
                ],
                "optional_fields": [
                    name
                    for name, field in model.model_fields.items()
                    if not field.is_required()
                ],
                "kpi_family": kpi_family,
            }
            for calculator, (model, kpi_family) in _CALCULATOR_CONTRACTS.items()
        },
        "non_evidence_classifications": ["irrelevant", "unsupported"],
    }


def list_tables(catalog: UploadCatalog) -> list[TableInspection]:
    """List table names, headers, row counts, and columns without returning row data."""
    return [
        TableInspection(
            source_name=table.source_name,
            header_row=table.header_row,
            row_count=table.row_count,
            columns=table.columns,
        )
        for table in catalog.tables
    ]


def describe_table(catalog: UploadCatalog, table_name: str) -> TableDescription:
    """Describe one table's columns and return at most five representative rows."""
    table = _table(catalog, table_name)
    return TableDescription(
        source_name=table.source_name,
        header_row=table.header_row,
        row_count=table.row_count,
        columns=[_describe_column(table, column) for column in table.columns],
        sample_rows=table.rows[:5],
    )


def inspect_tables(
    catalog: UploadCatalog,
    table_names: list[str],
) -> list[TableAnalysis]:
    """Describe and profile several selected tables in one bounded operation."""
    analyses: list[TableAnalysis] = []
    for table_name in table_names:
        description = describe_table(catalog, table_name)
        analyses.append(
            TableAnalysis(
                description=description.model_copy(
                    update={"sample_rows": description.sample_rows[:3]}
                ),
                profile=profile_data(catalog, table_name),
            )
        )
    return analyses


def validate_classifications(
    catalog: UploadCatalog,
    classifications: list[TableClassification],
) -> list[ClassificationValidation]:
    """Validate the complete table classification and execution plan."""
    validations: list[ClassificationValidation] = []
    known_sources = {table.source_name for table in catalog.tables}
    classified_sources = [item.source_name for item in classifications]
    for classification in classifications:
        if classification.source_name not in known_sources:
            validations.append(
                ClassificationValidation(
                    source_name=classification.source_name,
                    kpi_family=classification.kpi_family,
                    valid=False,
                    unknown_source_columns=[],
                    duplicate_source_columns=[],
                    missing_required_fields=[],
                    invalid_calculators=[],
                    message="The classified source table does not exist.",
                )
            )
            continue
        validations.append(validate_classification(catalog, classification))
    for source_name in sorted(known_sources):
        count = classified_sources.count(source_name)
        if count == 1:
            continue
        validations.append(
            ClassificationValidation(
                source_name=source_name,
                kpi_family="unclassified" if count == 0 else "duplicate",
                valid=False,
                unknown_source_columns=[],
                duplicate_source_columns=[],
                missing_required_fields=[],
                invalid_calculators=[],
                message=(
                    "Every source table must be classified exactly once."
                    if count == 0
                    else "A source table cannot have multiple classifications."
                ),
            )
        )
    return validations


def get_rows(
    catalog: UploadCatalog,
    table_name: str,
    columns: list[str] | None,
    filters: dict[str, str] | None,
    sort_by: str | None,
    descending: bool,
    limit: int,
) -> RowPage:
    """Return a bounded, optionally filtered and sorted page of source rows."""
    table = _table(catalog, table_name)
    selected_columns = columns or table.columns
    _require_columns(table, selected_columns)
    if filters:
        _require_columns(table, list(filters))
    if sort_by:
        _require_columns(table, [sort_by])

    matching_rows = [
        row
        for row in table.rows
        if not filters
        or all(_matches(row.get(column), value) for column, value in filters.items())
    ]
    if sort_by:
        matching_rows.sort(
            key=lambda row: (row.get(sort_by) is None, str(row.get(sort_by)).casefold()),
            reverse=descending,
        )
    page_rows = [
        {column: row.get(column) for column in [*selected_columns, "_source_row"]}
        for row in matching_rows[:limit]
    ]
    return RowPage(
        source_name=table.source_name,
        columns=[*selected_columns, "_source_row"],
        rows=page_rows,
        total_matching_rows=len(matching_rows),
        truncated=len(matching_rows) > limit,
    )


def profile_data(catalog: UploadCatalog, table_name: str) -> TableProfile:
    """Profile blanks, duplicate rows, and likely ID, date, and numeric columns."""
    table = _table(catalog, table_name)
    descriptions = [_describe_column(table, column) for column in table.columns]
    duplicate_count = len(table.rows) - len(
        {
            tuple(row.get(column) for column in table.columns)
            for row in table.rows
        }
    )
    return TableProfile(
        source_name=table.source_name,
        blank_columns=[
            description.name
            for description in descriptions
            if description.missing_count == table.row_count
        ],
        duplicate_row_count=duplicate_count,
        likely_id_columns=[
            description.name
            for description in descriptions
            if _looks_like_id(description, table.row_count)
        ],
        date_like_columns=[
            description.name
            for description in descriptions
            if description.inferred_type == "date"
        ],
        numeric_columns=[
            description.name
            for description in descriptions
            if description.inferred_type == "number"
        ],
    )


def search_rows(
    catalog: UploadCatalog,
    query: str,
    table_name: str | None,
    limit: int,
) -> list[RowPage]:
    """Find a text fragment across one table or all tables, returning bounded rows."""
    normalized_query = query.casefold()
    tables = [_table(catalog, table_name)] if table_name else catalog.tables
    matches: list[RowPage] = []
    for table in tables:
        matching_rows = [
            row
            for row in table.rows
            if any(
                normalized_query in str(row.get(column, "")).casefold()
                for column in table.columns
            )
        ]
        if matching_rows:
            matches.append(
                RowPage(
                    source_name=table.source_name,
                    columns=[*table.columns, "_source_row"],
                    rows=matching_rows[:limit],
                    total_matching_rows=len(matching_rows),
                    truncated=len(matching_rows) > limit,
                )
            )
    return matches


def get_distinct_values(
    catalog: UploadCatalog,
    table_name: str,
    column: str,
    limit: int,
) -> DistinctValues:
    """Return a bounded list of non-empty distinct values for one column."""
    table = _table(catalog, table_name)
    _require_columns(table, [column])
    values = _unique_values(row.get(column) for row in table.rows)
    return DistinctValues(
        source_name=table.source_name,
        column=column,
        values=values[:limit],
        total_distinct_values=len(values),
        truncated=len(values) > limit,
    )


def validate_classification(
    catalog: UploadCatalog,
    classification: TableClassification,
) -> ClassificationValidation:
    """Validate a classification and its calculator-specific field bindings."""
    table = _table(catalog, classification.source_name)
    if classification.kpi_family in {"irrelevant", "unsupported"}:
        valid = (
            not classification.calculator_invocations
        )
        return ClassificationValidation(
            source_name=table.source_name,
            kpi_family=classification.kpi_family,
            valid=valid,
            unknown_source_columns=[],
            duplicate_source_columns=[],
            missing_required_fields=[],
            invalid_calculators=([] if valid else [
                invocation.calculator
                for invocation in classification.calculator_invocations
            ]),
            message=(
                "Non-evidence table classification is valid."
                if valid
                else "Irrelevant and unsupported tables cannot invoke calculators."
            ),
        )
    unknown_source_columns: set[str] = set()
    duplicate_source_columns: set[str] = set()
    missing_required_fields: set[str] = set()
    invalid_calculators: list[str] = []
    for invocation in classification.calculator_invocations:
        contract = _CALCULATOR_CONTRACTS.get(invocation.calculator)
        if contract is None or contract[1] != classification.kpi_family:
            invalid_calculators.append(invocation.calculator)
            continue
        model, _ = contract
        bindings = invocation.field_bindings
        unknown_source_columns.update(set(bindings.values()) - set(table.columns))
        duplicate_source_columns.update(
            source_column
            for source_column in set(bindings.values())
            if list(bindings.values()).count(source_column) > 1
        )
        required_fields = {
            name for name, field in model.model_fields.items() if field.is_required()
        }
        missing_required_fields.update(required_fields - set(bindings))
    if not classification.calculator_invocations:
        invalid_calculators.append("missing_calculator")
    valid = not (
        unknown_source_columns
        or duplicate_source_columns
        or missing_required_fields
        or invalid_calculators
    )
    return ClassificationValidation(
        source_name=table.source_name,
        kpi_family=classification.kpi_family,
        valid=valid,
        unknown_source_columns=sorted(unknown_source_columns),
        duplicate_source_columns=sorted(duplicate_source_columns),
        missing_required_fields=sorted(missing_required_fields),
        invalid_calculators=invalid_calculators,
        message=(
            "Classification and calculator bindings are structurally valid."
            if valid
            else "Classification or calculator bindings need correction."
        ),
    )


def _table(catalog: UploadCatalog, table_name: str) -> CatalogTable:
    for table in catalog.tables:
        if table.source_name == table_name:
            return table
    available = ", ".join(table.source_name for table in catalog.tables)
    raise ValueError(f"Table '{table_name}' was not found. Available tables: {available}.")


def _require_columns(table: CatalogTable, columns: list[str]) -> None:
    unknown_columns = sorted(set(columns) - set(table.columns))
    if unknown_columns:
        raise ValueError(
            f"Unknown columns in '{table.source_name}': {', '.join(unknown_columns)}."
        )


def _describe_column(table: CatalogTable, column: str) -> ColumnDescription:
    values = [row.get(column) for row in table.rows]
    non_empty_values = [value for value in values if value is not None]
    return ColumnDescription(
        name=column,
        inferred_type=_infer_type(non_empty_values),
        missing_count=len(values) - len(non_empty_values),
        unique_count=len(_unique_values(non_empty_values)),
    )


def _infer_type(values: Sequence[CellValue]) -> str:
    if not values:
        return "empty"
    if all(isinstance(value, bool) for value in values):
        return "boolean"
    if all(_is_number(value) for value in values):
        return "number"
    if all(isinstance(value, str) and _is_iso_date(value) for value in values):
        return "date"
    return "text"


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_number(value: CellValue) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if not isinstance(value, str):
        return False
    try:
        float(value)
    except ValueError:
        return False
    return True


def _looks_like_id(description: ColumnDescription, row_count: int) -> bool:
    normalized_name = description.name.casefold().replace("_", "").replace(" ", "")
    return (
        normalized_name.endswith("id")
        or (
            row_count > 0
            and description.missing_count == 0
            and description.unique_count == row_count
        )
    )


def _matches(value: CellValue | None, expected: str) -> bool:
    return value is not None and str(value).casefold() == expected.casefold()


def _unique_values(values: Iterable[CellValue]) -> list[CellValue]:
    unique_values: list[CellValue] = []
    for value in values:
        if value is not None and value not in unique_values:
            unique_values.append(value)
    return unique_values
