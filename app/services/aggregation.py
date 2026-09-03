from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
import json

from pydantic import BaseModel

from app.core.storage import (
    CanonicalRecordWrite,
    StoredAggregationState,
)
from app.schemas.performance import (
    AttendanceComplianceEvidence,
    Employee,
    LeaveComplianceEvidence,
    PerformanceEvidenceDataset,
    PerformanceTarget,
    QualityEvidence,
    SubmissionComplianceEvidence,
    ValidationFinding,
    WorkOutputEvidence,
)
from app.schemas.uploads import CalculationPlan, SchemaMappingSummary


@dataclass(frozen=True, slots=True)
class RecordSpec:
    record_type: str
    collection_name: str
    model: type[BaseModel]
    identity_field: str
    start_field: str | None
    end_field: str | None


@dataclass(frozen=True, slots=True)
class MaterializedAggregation:
    dataset: PerformanceEvidenceDataset
    mapping_summaries: list[SchemaMappingSummary]
    limitations: list[str]


_RECORD_SPECS = (
    RecordSpec("employee", "employees", Employee, "employee_id", None, None),
    RecordSpec(
        "performance_target",
        "performance_targets",
        PerformanceTarget,
        "employee_id",
        None,
        None,
    ),
    RecordSpec(
        "work_output",
        "work_outputs",
        WorkOutputEvidence,
        "record_id",
        "assigned_date",
        "assigned_date",
    ),
    RecordSpec(
        "attendance",
        "attendance_events",
        AttendanceComplianceEvidence,
        "record_id",
        "occurred_on",
        "occurred_on",
    ),
    RecordSpec(
        "required_report",
        "submission_events",
        SubmissionComplianceEvidence,
        "record_id",
        "due_date",
        "due_date",
    ),
    RecordSpec(
        "leave",
        "leave_events",
        LeaveComplianceEvidence,
        "record_id",
        "start_date",
        "end_date",
    ),
    RecordSpec(
        "quality_review",
        "quality_events",
        QualityEvidence,
        "record_id",
        "occurred_on",
        "occurred_on",
    ),
)
_SPEC_BY_TYPE = {spec.record_type: spec for spec in _RECORD_SPECS}
_COLLECTION_BY_CALCULATOR = {
    "load_employees": "employees",
    "load_performance_targets": "performance_targets",
    "calculate_productivity": "work_outputs",
    "calculate_attendance_compliance": "attendance_events",
    "calculate_submission_compliance": "submission_events",
    "calculate_leave_compliance": "leave_events",
    "calculate_quality": "quality_events",
}


def canonicalize_batch(
    dataset: PerformanceEvidenceDataset,
) -> tuple[PerformanceEvidenceDataset, list[ValidationFinding]]:
    """Collapse same-ID replays, reject same-ID conflicts, and flag content duplicates."""
    updates: dict[str, list[BaseModel]] = {}
    findings: list[ValidationFinding] = []
    for spec in _RECORD_SPECS:
        records = list(getattr(dataset, spec.collection_name))
        grouped: dict[str, list[BaseModel]] = {}
        for record in records:
            grouped.setdefault(str(getattr(record, spec.identity_field)), []).append(record)

        accepted: list[BaseModel] = []
        for record_id, versions in grouped.items():
            first = versions[0]
            if all(version == first for version in versions[1:]):
                accepted.append(first)
                if len(versions) > 1:
                    findings.append(
                        ValidationFinding(
                            code="duplicate_canonical_record",
                            severity="warning",
                            message=(
                                "Identical same-ID rows in this batch were collapsed before publication."
                            ),
                            employee_id=str(getattr(first, "employee_id")),
                            record_ids=[record_id],
                            source_type=spec.record_type,
                            scoring_impact="excluded_from_scoring",
                        )
                    )
                continue

            for employee_id in sorted(
                {str(getattr(version, "employee_id")) for version in versions}
            ):
                findings.append(
                    ValidationFinding(
                        code="conflicting_canonical_record",
                        severity="error",
                        message=(
                            "Conflicting rows share one stable identity in this batch; "
                            "that identity was not published."
                        ),
                        employee_id=employee_id,
                        record_ids=[record_id],
                        source_type=spec.record_type,
                        scoring_impact="blocks_score",
                    )
                )

        if spec.identity_field == "record_id":
            findings.extend(_content_duplicate_findings(spec, accepted))
        updates[spec.collection_name] = accepted

    return dataset.model_copy(update=updates), findings


def canonical_record_writes(
    dataset: PerformanceEvidenceDataset,
) -> list[CanonicalRecordWrite]:
    """Serialize a validated batch into mechanical canonical-record writes."""
    writes: list[CanonicalRecordWrite] = []
    for spec in _RECORD_SPECS:
        for record in getattr(dataset, spec.collection_name):
            start = getattr(record, spec.start_field) if spec.start_field else None
            end = getattr(record, spec.end_field) if spec.end_field else None
            writes.append(
                CanonicalRecordWrite(
                    record_type=spec.record_type,
                    record_id=str(getattr(record, spec.identity_field)),
                    employee_id=str(getattr(record, "employee_id")),
                    period_start=_date_string(start),
                    period_end=_date_string(end),
                    payload_json=record.model_dump_json(),
                    source_version=getattr(record, "source_version", None),
                    source_updated_at=_datetime_string(
                        getattr(record, "source_updated_at", None)
                    ),
                )
            )
    return writes


def materialize_aggregation(
    state: StoredAggregationState,
) -> MaterializedAggregation:
    """Validate canonical payloads and rebuild one combined evidence dataset."""
    collections: dict[str, list[BaseModel]] = {
        spec.collection_name: [] for spec in _RECORD_SPECS
    }
    contributing_schemas: dict[str, set[str]] = {
        spec.collection_name: set() for spec in _RECORD_SPECS
    }
    for stored in state.records:
        spec = _SPEC_BY_TYPE[stored.record_type]
        collections[spec.collection_name].append(
            spec.model.model_validate_json(stored.payload_json)
        )
        contributing_schemas[spec.collection_name].add(stored.schema_fingerprint)

    plans = {
        item.schema_fingerprint: CalculationPlan.model_validate_json(item.plan_json)
        for item in state.mapping_summaries
    }
    fields_by_schema: dict[str, dict[str, set[str]]] = {
        fingerprint: _mapped_fields(plan) for fingerprint, plan in plans.items()
    }
    mapped_fields: dict[str, set[str]] = {}
    limitations: list[str] = []
    for collection_name, fingerprints in contributing_schemas.items():
        field_sets = [
            fields_by_schema[fingerprint].get(collection_name, set())
            for fingerprint in sorted(fingerprints)
        ]
        if not field_sets:
            continue
        mapped_fields[collection_name] = set.intersection(*field_sets)
        if any(field_set != field_sets[0] for field_set in field_sets[1:]):
            limitations.append(
                "Mixed schemas provide different optional bindings for "
                f"{collection_name}; only their shared mapped fields were used."
            )

    dataset = PerformanceEvidenceDataset.model_validate(
        {**collections, "mapped_fields": mapped_fields}
    )
    mapping_summaries = [
        SchemaMappingSummary(
            schema_fingerprint=item.schema_fingerprint,
            included_submission_count=item.included_submission_count,
            selected_tables=plans[item.schema_fingerprint].selected_tables,
            table_classifications=plans[item.schema_fingerprint].table_classifications,
        )
        for item in state.mapping_summaries
    ]
    return MaterializedAggregation(
        dataset=dataset,
        mapping_summaries=mapping_summaries,
        limitations=limitations,
    )


def _content_duplicate_findings(
    spec: RecordSpec,
    records: list[BaseModel],
) -> list[ValidationFinding]:
    grouped: dict[str, list[BaseModel]] = {}
    for record in records:
        content = record.model_dump(exclude={"record_id"}, mode="json")
        fingerprint = sha256(
            json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        grouped.setdefault(fingerprint, []).append(record)

    findings: list[ValidationFinding] = []
    for duplicates in grouped.values():
        if len(duplicates) < 2:
            continue
        employee_ids = {str(getattr(item, "employee_id")) for item in duplicates}
        for employee_id in sorted(employee_ids):
            employee_records = [
                item
                for item in duplicates
                if str(getattr(item, "employee_id")) == employee_id
            ]
            if len(employee_records) < 2:
                continue
            findings.append(
                ValidationFinding(
                    code="duplicate_record_content",
                    severity="warning",
                    message=(
                        "Different record IDs contain identical evidence; review them "
                        "before deciding whether either event should be removed."
                    ),
                    employee_id=employee_id,
                    record_ids=[
                        str(getattr(item, "record_id")) for item in employee_records
                    ],
                    source_type=spec.record_type,
                    scoring_impact="none",
                )
            )
    return findings


def _mapped_fields(plan: CalculationPlan) -> dict[str, set[str]]:
    mapped: dict[str, set[str]] = {}
    for classification in plan.table_classifications:
        for invocation in classification.calculator_invocations:
            collection_name = _COLLECTION_BY_CALCULATOR[invocation.calculator]
            mapped.setdefault(collection_name, set()).update(
                invocation.field_bindings
            )
    return mapped


def _date_string(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _datetime_string(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
