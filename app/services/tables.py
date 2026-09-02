from app.schemas.tables import AnalyzeTablesRequest
from app.schemas.uploads import CatalogTable, DataCatalog


def catalog_from_tables(request: AnalyzeTablesRequest) -> DataCatalog:
    """Convert validated table rows into the transport-neutral analysis catalog."""
    tables: list[CatalogTable] = []
    for received_table in request.tables:
        columns = list(
            dict.fromkeys(column for row in received_table.rows for column in row)
        )
        rows = [
            {**row, "_source_row": row_number}
            for row_number, row in enumerate(received_table.rows, start=1)
        ]
        tables.append(
            CatalogTable(
                source_name=received_table.source_name,
                header_row=None,
                row_count=len(rows),
                columns=columns,
                rows=rows,
            )
        )
    return DataCatalog(tables=tables)
