from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.uploads import CellValue

type SourceName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class ReceivedTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: SourceName
    rows: list[dict[str, CellValue]] = Field(min_length=1, max_length=100_000)

    @model_validator(mode="after")
    def validate_columns(self) -> Self:
        columns = {column for row in self.rows for column in row}
        if not columns:
            raise ValueError("A table must contain at least one column.")
        if "_source_row" in columns:
            raise ValueError("_source_row is reserved for internal row tracking.")
        if any(not column.strip() for column in columns):
            raise ValueError("Column names cannot be blank.")
        if len(columns) > 250:
            raise ValueError("A table cannot contain more than 250 columns.")
        return self


class AnalyzeTablesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tables: list[ReceivedTable] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_tables(self) -> Self:
        normalized_names = [table.source_name.casefold() for table in self.tables]
        if len(normalized_names) != len(set(normalized_names)):
            raise ValueError("Table source names must be unique.")
        if sum(len(table.rows) for table in self.tables) > 100_000:
            raise ValueError("A request cannot contain more than 100,000 rows.")
        return self
