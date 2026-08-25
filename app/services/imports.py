from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from math import isnan
from numbers import Number
from pathlib import PurePath

import pandas as pd

from app.core.errors import AppError
from app.schemas.uploads import (
    CatalogTable,
    CellValue,
    UploadCatalog,
)
from app.services.uploads import accept_upload


class UnparseableFileError(AppError):
    """The upload cannot be read as the declared CSV or Excel format."""

    status_code = 422
    code = "unparseable_file"


def parse_upload(
    file_name: str | None,
    contents: bytes,
    maximum_bytes: int,
) -> UploadCatalog:
    """Parse an upload into a request-scoped catalog without assigning business meaning."""
    receipt = accept_upload(file_name, contents, maximum_bytes)
    raw_tables = _read_tables(receipt.file_type, contents)
    return UploadCatalog(
        file_name=receipt.file_name,
        file_type=receipt.file_type,
        byte_size=receipt.byte_size,
        tables=[_catalog_table(raw_table) for raw_table in raw_tables],
    )


@dataclass(frozen=True)
class _RawTable:
    name: str
    header_row: int | None
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
        return _RawTable(name=name, header_row=None, frame=pd.DataFrame())
    columns = _unique_columns(raw.iloc[header_index].tolist())
    frame = raw.iloc[header_index + 1 :].copy()
    frame.columns = columns
    return _RawTable(
        name=name,
        header_row=header_index + 1,
        frame=frame.dropna(how="all"),
    )


def _catalog_table(raw_table: _RawTable) -> CatalogTable:
    return CatalogTable(
        source_name=raw_table.name,
        header_row=raw_table.header_row,
        row_count=len(raw_table.frame),
        columns=[str(column) for column in raw_table.frame.columns],
        rows=_records(raw_table.frame),
    )


def _find_header_row(raw: pd.DataFrame) -> int | None:
    for index in range(min(len(raw), 20)):
        values = [
            value
            for value in raw.iloc[index].tolist()
            if pd.notna(value) and str(value).strip()
        ]
        if len(values) >= 2:
            return index
    return None


def _unique_columns(values: list[object]) -> list[str]:
    names: list[str] = []
    counts: dict[str, int] = {}
    for index, value in enumerate(values, start=1):
        base_name = str(value).strip() or f"unnamed_column_{index}"
        counts[base_name] = counts.get(base_name, 0) + 1
        suffix = counts[base_name]
        names.append(base_name if suffix == 1 else f"{base_name}_{suffix}")
    return names


def _records(frame: pd.DataFrame) -> list[dict[str, CellValue]]:
    records: list[dict[str, CellValue]] = []
    for row_number, row in enumerate(frame.to_dict(orient="records"), start=1):
        record = {str(column): _cell_value(value) for column, value in row.items()}
        record["_source_row"] = row_number
        records.append(record)
    return records


def _cell_value(value: object) -> CellValue:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, bool):
        return value
    if isinstance(value, Number):
        numeric_value = float(str(value))
        if isnan(numeric_value):
            return None
        return int(numeric_value) if numeric_value.is_integer() else numeric_value
    return str(value)
