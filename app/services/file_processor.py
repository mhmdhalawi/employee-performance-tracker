import io
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.core.config import get_settings
from app.core.errors import (
    FileParseError,
    FileTooLargeError,
    SchemaValidationError,
    UnsupportedFileTypeError,
)
from app.schemas.common import NormalizedRecord, RowIssue
from app.schemas.mapping import ColumnPreview
from app.services.profiles import (
    ColumnMapping,
    RoleProfile,
    build_column_mapping,
    detect_profile,
    get_profile,
)
from app.utils.numbers import coerce_float


@dataclass
class ProcessedFile:
    """Everything the upload route needs from ingestion."""

    profile: RoleProfile
    profile_detected: bool
    mapping: ColumnMapping
    records: list[NormalizedRecord]
    issues: list[RowIssue]
    row_count: int


def validate_upload(filename: str, content: bytes) -> None:
    """Guard extension and size before any parsing happens.

    Raises UnsupportedFileTypeError / FileTooLargeError.
    """
    settings = get_settings()
    suffix = Path(filename).suffix.lower()

    if suffix not in settings.allowed_upload_extensions:
        raise UnsupportedFileTypeError(
            f"Unsupported file type {suffix or '(none)'!r}.",
            {"allowed": settings.allowed_upload_extensions, "filename": filename},
        )

    if not content:
        raise FileParseError("Uploaded file is empty.", {"filename": filename})

    if len(content) > settings.max_upload_bytes:
        raise FileTooLargeError(
            "Uploaded file exceeds the size limit.",
            {"size": len(content), "limit": settings.max_upload_bytes},
        )


def read_table(filename: str, content: bytes) -> pd.DataFrame:
    """Read CSV/Excel bytes into a DataFrame with all cells kept as-is.

    ``dtype=str`` is intentional: numeric coercion happens in one place
    (``coerce_float``) so that bad cells become reportable issues rather than
    silent NaNs.
    """
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".csv":
            frame = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=True)
        else:
            frame = pd.read_excel(io.BytesIO(content), dtype=str)
    except Exception as exc:  # pandas raises a wide variety of parser errors
        raise FileParseError(
            f"Could not read {filename!r} as a table.", {"reason": str(exc)}
        ) from exc

    frame = frame.dropna(how="all")
    if frame.empty:
        raise FileParseError("File contains no data rows.", {"filename": filename})

    frame.columns = [str(c).strip() for c in frame.columns]
    return frame


def load_frame(filename: str, content: bytes) -> pd.DataFrame:
    """Validate then parse an upload. Raises AppError subclasses for unusable files."""
    validate_upload(filename, content)
    return read_table(filename, content)


def column_previews(
    frame: pd.DataFrame, sample_size: int = 6
) -> list[ColumnPreview]:
    """Summarize each column so the mapping agent can reason about it.

    Values are sampled, not sent wholesale: the agent needs enough to judge unit and scale,
    not the whole file.
    """
    previews: list[ColumnPreview] = []

    for column in frame.columns:
        series = frame[column]
        non_empty = [
            str(v).strip()
            for v in series.tolist()
            if v is not None and not pd.isna(v) and str(v).strip()
        ]
        numbers = [n for n in (coerce_float(v) for v in non_empty) if n is not None]

        previews.append(
            ColumnPreview(
                column=str(column),
                non_empty=len(non_empty),
                numeric_ratio=(len(numbers) / len(non_empty)) if non_empty else 0.0,
                sample_values=non_empty[:sample_size],
                numeric_min=min(numbers) if numbers else None,
                numeric_max=max(numbers) if numbers else None,
                numeric_mean=(round(sum(numbers) / len(numbers), 4) if numbers else None),
            )
        )

    return previews


def _cell(row: pd.Series, column: str | None) -> str | None:
    if not column or column not in row.index:
        return None
    value = row[column]
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def normalize_frame(
    frame: pd.DataFrame,
    profile: RoleProfile,
    mapping: ColumnMapping,
) -> tuple[list[NormalizedRecord], list[RowIssue]]:
    """Turn a DataFrame into NormalizedRecords, collecting per-row issues.

    A row with a bad cell is still scored on its remaining metrics; the bad cell
    is reported. A row without an employee id is skipped with an ``error`` issue,
    because there is nothing to attribute the numbers to.
    """
    records: list[NormalizedRecord] = []
    issues: list[RowIssue] = []

    for position, (_, row) in enumerate(frame.iterrows()):
        row_number = position + 2  # +1 for 0-index, +1 for the header line

        employee_id = _cell(row, mapping.id_column)
        if not employee_id:
            issues.append(
                RowIssue(
                    row=row_number,
                    column=mapping.id_column,
                    severity="error",
                    message="Missing employee identifier; row skipped.",
                )
            )
            continue

        metrics: dict[str, float] = {}
        for metric_name, source_column in mapping.metric_columns.items():
            raw = _cell(row, source_column)
            if raw is None:
                continue
            value = coerce_float(raw)
            if value is None:
                issues.append(
                    RowIssue(
                        row=row_number,
                        column=source_column,
                        severity="warning",
                        message=(
                            f"Value {raw!r} is not numeric; metric "
                            f"{metric_name!r} excluded from scoring."
                        ),
                    )
                )
                continue
            metrics[metric_name] = value

        if not metrics:
            issues.append(
                RowIssue(
                    row=row_number,
                    severity="warning",
                    message="No recognizable metric values in this row.",
                )
            )

        records.append(
            NormalizedRecord(
                employee_id=employee_id,
                employee_name=_cell(row, mapping.name_column),
                profile=profile.key,
                period=_cell(row, mapping.period_column),
                metrics=metrics,
                source_row=row_number,
                raw={str(k): _cell(row, str(k)) for k in frame.columns},
            )
        )

    return records, issues


def process_file(
    filename: str,
    content: bytes,
    profile_key: str | None = None,
) -> ProcessedFile:
    """Validate, parse and normalize an uploaded file.

    Pass ``profile_key`` to force a role profile; otherwise it is inferred from
    the file's columns. Raises AppError subclasses for unusable files; row-level
    problems come back in ``issues``.
    """
    frame = load_frame(filename, content)
    headers = [str(c) for c in frame.columns]

    if profile_key:
        profile = get_profile(profile_key)
        detected = False
    else:
        profile, matched = detect_profile(headers)
        detected = True
        if matched == 0:
            raise SchemaValidationError(
                "Could not match any known metric columns to a role profile. "
                "Send an explicit 'profile' value or rename the columns.",
                {"headers": headers, "available_profiles": ["support", "developer"]},
            )

    mapping = build_column_mapping(headers, profile)
    if mapping.id_column is None:
        raise SchemaValidationError(
            "No employee identifier column found.",
            {"expected_any_of": list(profile.id_aliases), "headers": headers},
        )

    records, issues = normalize_frame(frame, profile, mapping)
    return ProcessedFile(
        profile=profile,
        profile_detected=detected,
        mapping=mapping,
        records=records,
        issues=issues,
        row_count=len(frame.index),
    )
