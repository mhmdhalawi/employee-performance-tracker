from datetime import date, datetime

from app.core.errors import EmployeeEvidenceNotFoundError, InvalidEmployeeEvidenceQueryError
from app.schemas.employee_evidence import (
    AttendanceRow,
    ComplianceRow,
    EmployeeEvidenceResponse,
    EmployeeEvidenceRow,
    EmployeeEvidenceTables,
    EvidenceTable,
    LeaveRow,
    QualityRow,
    SubmissionRow,
    WorkOutputRow,
)
from app.schemas.performance import PerformanceEvidenceDataset, ValidationFinding
from app.schemas.uploads import AnalysisFilters
from app.services.performance.scope import (
    duplicate_attendance_ids,
    employee_evidence,
    quality_excluded,
)
from app.services.performance.validation import validate_dataset
from app.services.submissions.dashboard import load_dashboard_context, resolve_dashboard_period
from app.utils.links import is_safe_evidence_link


def build_employee_evidence_tables(
    dataset: PerformanceEvidenceDataset,
    employee_id: str,
    start_date: date | None,
    end_date: date | None,
) -> EmployeeEvidenceTables:
    """Build complete employee tables with the same scope/exclusions as scoring."""
    findings = validate_dataset(dataset)
    known_output_ids = {output.record_id for output in dataset.work_outputs}
    duplicate_ids = duplicate_attendance_ids(findings)
    evidence = employee_evidence(
        dataset, employee_id, start_date, end_date, duplicate_ids, include_excluded=True
    )

    def row_findings(record_id: str, source_type: str) -> list[ValidationFinding]:
        return [
            finding
            for finding in findings
            if finding.employee_id == employee_id
            and record_id in finding.record_ids
            and finding.source_type in (source_type, "source_records")
        ]

    productivity = [
        WorkOutputRow(
            record_id=record.record_id,
            record=record.model_copy(
                update={
                    "evidence_link": record.evidence_link
                    if is_safe_evidence_link(record.evidence_link)
                    else None,
                }
            ),
            validation_findings=row_findings(record.record_id, "productivity_evidence"),
        )
        for record in evidence.projects
    ]
    compliance: list[ComplianceRow] = [
        AttendanceRow(
            record_id=record.record_id,
            record=record,
            validation_findings=row_findings(record.record_id, "attendance"),
            excluded_from_scoring=record.record_id in duplicate_ids,
            exclusion_reason="Excluded duplicate attendance record."
            if record.record_id in duplicate_ids
            else None,
        )
        for record in evidence.attendance
    ]
    compliance.extend(
        SubmissionRow(
            record_id=record.record_id,
            record=record,
            validation_findings=row_findings(record.record_id, "submission_evidence"),
        )
        for record in evidence.reports
    )
    compliance.extend(
        LeaveRow(
            record_id=record.record_id,
            record=record,
            validation_findings=row_findings(record.record_id, "leave_evidence"),
        )
        for record in evidence.leave
    )
    quality = [
        QualityRow(
            record_id=record.record_id,
            record=record,
            validation_findings=row_findings(record.record_id, "quality_evidence"),
            excluded_from_scoring=quality_excluded(record, known_output_ids),
            exclusion_reason="Related work output is absent from canonical evidence."
            if quality_excluded(record, known_output_ids)
            else None,
        )
        for record in evidence.reviews
    ]
    return EmployeeEvidenceTables(
        productivity=EvidenceTable(
            total_count=len(productivity), rows=sort_evidence_rows(productivity)
        ),
        compliance=EvidenceTable(total_count=len(compliance), rows=sort_evidence_rows(compliance)),
        quality=EvidenceTable(total_count=len(quality), rows=sort_evidence_rows(quality)),
    )


def sort_evidence_rows[Row: EmployeeEvidenceRow](rows: list[Row]) -> list[Row]:
    """Order dates descending with stable ascending type/identity tie-breakers."""

    def key(row: Row) -> tuple[int, str, str]:
        record = row.record
        if isinstance(row, WorkOutputRow):
            business_date = row.record.assigned_date
        elif isinstance(row, SubmissionRow):
            business_date = row.record.due_date
        elif isinstance(row, LeaveRow):
            business_date = row.record.start_date
        else:
            business_date = record.occurred_on
        return -business_date.toordinal(), row.record_type, row.record_id

    return sorted(rows, key=key)


async def get_employee_evidence(
    employee_id: str,
    kpi: str,
    page: int = 1,
    page_size: int = 5,
    start_date: date | None = None,
    end_date: date | None = None,
    period_weeks: int | None = None,
) -> EmployeeEvidenceResponse:
    """Read a bounded evidence page; raise typed errors for unknown employees or bad paging."""
    if kpi not in ("productivity", "compliance", "quality"):
        raise InvalidEmployeeEvidenceQueryError("kpi must be productivity, compliance, or quality.")
    if page < 1 or not 1 <= page_size <= 50:
        raise InvalidEmployeeEvidenceQueryError("page must be positive and page_size must be 1-50.")
    context = load_dashboard_context()
    dataset = context.materialized.dataset
    employee = next((row for row in dataset.employees if row.employee_id == employee_id), None)
    if employee is None:
        raise EmployeeEvidenceNotFoundError(f"Employee '{employee_id}' is not available.")
    resolved_start, resolved_end = resolve_dashboard_period(
        context, start_date, end_date, period_weeks
    )
    tables = build_employee_evidence_tables(dataset, employee_id, resolved_start, resolved_end)
    table = getattr(tables, kpi)
    offset = (page - 1) * page_size
    if offset >= table.total_count and page != 1:
        raise InvalidEmployeeEvidenceQueryError("The requested evidence page is out of range.")
    return EmployeeEvidenceResponse(
        employee=employee,
        kpi=kpi,
        page=page,
        page_size=page_size,
        applied_filters=AnalysisFilters(
            employee_id=employee_id,
            team=None,
            start_date=resolved_start,
            end_date=resolved_end,
            period_weeks=period_weeks,
        ),
        latest_submission_at=datetime.fromisoformat(context.state.latest_submission_at),
        total_count=table.total_count,
        rows=table.rows[offset : offset + page_size],
    )
