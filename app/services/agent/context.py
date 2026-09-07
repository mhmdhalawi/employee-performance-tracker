from app.schemas.uploads import (
    CatalogTable,
    ClassificationValidation,
    ColumnDescription,
    DataCatalog,
)
from app.services import catalog


def build_workbook_context(upload_catalog: DataCatalog) -> dict[str, object]:
    analyses = catalog.inspect_tables(
        upload_catalog,
        [table.source_name for table in upload_catalog.tables],
    )
    tables_by_source = {table.source_name: table for table in upload_catalog.tables}
    return {
        "classification_and_calculator_contract": catalog.classification_contract(),
        "tables": [
            _build_table_context(
                tables_by_source[analysis.description.source_name],
                analysis.description.columns,
                include_examples=False,
            )
            for analysis in analyses
        ],
    }


def build_targeted_repair_context(
    upload_catalog: DataCatalog,
    target_sources: set[str],
) -> dict[str, object]:
    analyses = catalog.inspect_tables(upload_catalog, sorted(target_sources))
    tables_by_source = {table.source_name: table for table in upload_catalog.tables}
    return {
        "tables": [
            _build_table_context(
                tables_by_source[analysis.description.source_name],
                analysis.description.columns,
                include_examples=True,
            )
            for analysis in analyses
        ]
    }


def repair_target_sources(
    upload_catalog: DataCatalog,
    invalid_classifications: list[ClassificationValidation],
) -> set[str]:
    known_sources = {table.source_name for table in upload_catalog.tables}
    if any(
        validation.source_name not in known_sources
        for validation in invalid_classifications
    ):
        return known_sources
    return {validation.source_name for validation in invalid_classifications}


def _build_table_context(
    table: CatalogTable,
    columns: list[ColumnDescription],
    include_examples: bool,
) -> dict[str, object]:
    return {
        "source_name": table.source_name,
        "row_count": table.row_count,
        "columns": [
            _build_column_context(table, column, include_examples) for column in columns
        ],
    }


def _build_column_context(
    table: CatalogTable,
    column: ColumnDescription,
    include_examples: bool,
) -> dict[str, object]:
    context: dict[str, object] = {
        "name": column.name,
        "type": column.inferred_type,
    }
    signals = _column_signals(table, column)
    if signals:
        context["signals"] = signals
    if include_examples:
        examples = _safe_categorical_examples(table, column, signals)
        if examples:
            context["examples"] = examples
    return context


def _column_signals(
    table: CatalogTable,
    column: ColumnDescription,
) -> list[str]:
    signals: list[str] = []
    normalized_name = column.name.casefold().replace("-", "_").replace(" ", "_")
    name_parts = [part for part in normalized_name.split("_") if part]
    if normalized_name.endswith("id") or (
        name_parts and name_parts[-1] in {"code", "identifier", "key", "ref"}
    ):
        signals.append("identifier_name")

    non_missing_count = table.row_count - column.missing_count
    if table.row_count and column.missing_count == table.row_count:
        signals.append("empty")
    elif table.row_count and column.missing_count * 2 >= table.row_count:
        signals.append("sparse")
    if non_missing_count and column.unique_count == 1:
        signals.append("constant")
    elif non_missing_count and column.unique_count == non_missing_count:
        signals.append("unique_values")
    elif column.inferred_type == "text" and 1 < column.unique_count <= 12:
        signals.append("low_cardinality")

    numeric_values = _numeric_values(table, column)
    if numeric_values and all(0 <= value <= 1 for value in numeric_values):
        signals.append("range_0_1")
    elif numeric_values and all(0 <= value <= 100 for value in numeric_values):
        signals.append("range_0_100")
    return signals


def _numeric_values(
    table: CatalogTable,
    column: ColumnDescription,
) -> list[float]:
    if column.inferred_type != "number":
        return []
    values: list[float] = []
    for row in table.rows:
        value = row.get(column.name)
        if value is None or isinstance(value, bool):
            continue
        try:
            values.append(float(value))
        except TypeError, ValueError:
            return []
    return values


def _safe_categorical_examples(
    table: CatalogTable,
    column: ColumnDescription,
    signals: list[str],
) -> list[str]:
    if (
        column.inferred_type != "text"
        or "identifier_name" in signals
        or "low_cardinality" not in signals
        or _is_sensitive_example_column(column.name)
    ):
        return []

    examples: list[str] = []
    for row in table.rows:
        value = row.get(column.name)
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if not normalized or normalized in examples:
            continue
        examples.append(normalized[:64])
        if len(examples) == 3:
            break
    return examples


def _is_sensitive_example_column(column_name: str) -> bool:
    normalized = column_name.casefold().replace("-", "_").replace(" ", "_")
    sensitive_markers = (
        "address",
        "comment",
        "description",
        "detail",
        "email",
        "employee",
        "link",
        "name",
        "note",
        "phone",
        "reason",
        "role",
        "staff",
        "team",
        "url",
        "user",
        "worker",
    )
    return any(marker in normalized for marker in sensitive_markers)

