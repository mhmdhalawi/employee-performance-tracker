from dataclasses import dataclass
from typing import Literal

type SubmissionStatus = Literal["pending", "completed", "failed"]


@dataclass(frozen=True, slots=True)
class CanonicalRecordWrite:
    record_type: str
    record_id: str
    employee_id: str
    period_start: str | None
    period_end: str | None
    payload_json: str
    source_version: int | None
    source_updated_at: str | None


@dataclass(frozen=True, slots=True)
class StoredCanonicalRecord:
    record_type: str
    record_id: str
    payload_json: str
    source_submission_id: str
    schema_fingerprint: str


@dataclass(frozen=True, slots=True)
class StoredSubmissionReceipt:
    submission_id: str
    status: SubmissionStatus
    received_at: str
    coverage_start: str | None
    coverage_end: str | None


@dataclass(frozen=True, slots=True)
class StoredMappingSummary:
    schema_fingerprint: str
    included_submission_count: int
    plan_json: str


@dataclass(frozen=True, slots=True)
class StoredAggregationState:
    records: list[StoredCanonicalRecord]
    mapping_summaries: list[StoredMappingSummary]
    included_submission_count: int
    latest_submission_at: str

