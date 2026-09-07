from collections import Counter
from collections.abc import Sequence
from datetime import date

from app.schemas.calculators import (
    CALCULATOR_BY_NAME,
    CALCULATORS,
    FOUNDATION_CALCULATORS,
)
from app.schemas.uploads import (
    CatalogTable,
    CellValue,
    ClassificationValidation,
    ColumnDescription,
    DataCatalog,
    TableAnalysis,
    TableClassification,
    TableDescription,
    TableProfile,
)


def classification_contract() -> dict[str, object]:
    """Return approved calculators and their KPI-family input contracts."""
    return {
        "approved_calculators": {
            spec.name: {
                "required_fields": spec.required_fields,
                "optional_fields": spec.optional_fields,
                "kpi_family": spec.kpi_family,
            }
            for spec in CALCULATORS
        },
        "non_evidence_classifications": ["irrelevant"],
    }


def describe_table(catalog: DataCatalog, table_name: str) -> TableDescription:
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
    catalog: DataCatalog,
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
    catalog: DataCatalog,
    classifications: list[TableClassification],
    *,
    available_foundation_calculators: set[str] | None = None,
) -> list[ClassificationValidation]:
    """Validate the complete table classification and execution plan."""
    validations: list[ClassificationValidation] = []
    known_sources = {table.source_name for table in catalog.tables}
    classification_counts = Counter(item.source_name for item in classifications)
    for classification in classifications:
        if classification.source_name not in known_sources:
            validations.append(
                _rejected_validation(
                    classification.source_name,
                    classification.kpi_family,
                    "The classified source table does not exist.",
                )
            )
            continue
        validations.append(validate_classification(catalog, classification))
    for source_name in sorted(known_sources):
        count = classification_counts[source_name]
        if count == 0:
            validations.append(
                _rejected_validation(
                    source_name,
                    "unclassified",
                    "Every source table must be classified exactly once.",
                )
            )
        elif count > 1:
            validations.append(
                _rejected_validation(
                    source_name,
                    "duplicate",
                    "A source table cannot have multiple classifications.",
                )
            )
    invoked_calculators = {
        invocation.calculator
        for classification in classifications
        for invocation in classification.calculator_invocations
    }
    if any(calculator.startswith("calculate_") for calculator in invoked_calculators):
        missing_foundations = sorted(
            FOUNDATION_CALCULATORS
            - invoked_calculators
            - (available_foundation_calculators or set())
        )
        if missing_foundations:
            validations.append(
                _rejected_validation(
                    "calculation_plan",
                    "shared",
                    "A KPI calculation plan requires employee and performance-target "
                    "loaders in the current plan or persisted canonical foundations.",
                    missing_required_fields=missing_foundations,
                )
            )
    return validations


def profile_data(catalog: DataCatalog, table_name: str) -> TableProfile:
    """Profile blanks, duplicate rows, and likely ID, date, and numeric columns."""
    table = _table(catalog, table_name)
    descriptions = [_describe_column(table, column) for column in table.columns]
    duplicate_count = len(table.rows) - len(
        {tuple(row.get(column) for column in table.columns) for row in table.rows}
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


def validate_classification(
    catalog: DataCatalog,
    classification: TableClassification,
) -> ClassificationValidation:
    """Validate a classification and its calculator-specific field bindings."""
    table = _table(catalog, classification.source_name)
    if classification.kpi_family == "irrelevant":
        forbidden_calculators = [
            invocation.calculator
            for invocation in classification.calculator_invocations
        ]
        if forbidden_calculators:
            message = "Irrelevant tables cannot invoke calculators."
        else:
            message = "Non-evidence table classification is valid."
        return ClassificationValidation(
            source_name=table.source_name,
            kpi_family=classification.kpi_family,
            valid=not forbidden_calculators,
            unknown_source_columns=[],
            duplicate_source_columns=[],
            missing_required_fields=[],
            invalid_calculators=forbidden_calculators,
            message=message,
        )
    unknown_source_columns: set[str] = set()
    duplicate_source_columns: set[str] = set()
    missing_required_fields: set[str] = set()
    invalid_calculators: list[str] = []
    for invocation in classification.calculator_invocations:
        spec = CALCULATOR_BY_NAME.get(invocation.calculator)
        if spec is None or spec.kpi_family != classification.kpi_family:
            invalid_calculators.append(invocation.calculator)
            continue
        bindings = invocation.field_bindings
        bound_column_counts = Counter(bindings.values())
        unknown_source_columns.update(set(bound_column_counts) - set(table.columns))
        duplicate_source_columns.update(
            source_column
            for source_column, count in bound_column_counts.items()
            if count > 1
        )
        missing_required_fields.update(set(spec.required_fields) - set(bindings))
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


def _rejected_validation(
    source_name: str,
    kpi_family: str,
    message: str,
    missing_required_fields: list[str] | None = None,
) -> ClassificationValidation:
    return ClassificationValidation(
        source_name=source_name,
        kpi_family=kpi_family,
        valid=False,
        unknown_source_columns=[],
        duplicate_source_columns=[],
        missing_required_fields=missing_required_fields or [],
        invalid_calculators=[],
        message=message,
    )


def _table(catalog: DataCatalog, table_name: str) -> CatalogTable:
    for table in catalog.tables:
        if table.source_name == table_name:
            return table
    available = ", ".join(table.source_name for table in catalog.tables)
    raise ValueError(
        f"Table '{table_name}' was not found. Available tables: {available}."
    )


def _describe_column(table: CatalogTable, column: str) -> ColumnDescription:
    values = [row.get(column) for row in table.rows]
    non_empty_values = [value for value in values if value is not None]
    return ColumnDescription(
        name=column,
        inferred_type=_infer_type(non_empty_values),
        missing_count=len(values) - len(non_empty_values),
        unique_count=len(set(non_empty_values)),
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
    return normalized_name.endswith("id") or (
        row_count > 0
        and description.missing_count == 0
        and description.unique_count == row_count
    )
