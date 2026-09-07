from collections import defaultdict
from typing import Literal

from app.schemas.performance import (
    PerformanceAlert,
    PerformanceEvidenceDataset,
    ValidationFinding,
)


def build_performance_alerts(
    dataset: PerformanceEvidenceDataset,
    findings: list[ValidationFinding],
    included_employee_ids: set[str],
    included_record_ids: set[str],
) -> list[PerformanceAlert]:
    """Convert relevant validation findings into traceable dashboard alerts."""
    employee_by_id = {employee.employee_id: employee for employee in dataset.employees}
    project_links = {
        record.record_id: record.evidence_link
        for record in dataset.work_outputs
        if record.evidence_link
    }
    severity_order = {"error": 0, "warning": 1, "info": 2}
    relevant = [
        finding
        for finding in findings
        if finding.employee_id in included_employee_ids
        and (
            not finding.record_ids
            or bool(set(finding.record_ids) & included_record_ids)
        )
    ]
    grouped: dict[
        tuple[
            str | None,
            str,
            Literal["error", "warning", "info"],
            str,
            Literal[
                "blocks_score",
                "excluded_from_scoring",
                "lowers_confidence",
                "affects_score",
                "none",
            ],
        ],
        list[ValidationFinding],
    ] = defaultdict(list)
    for finding in relevant:
        grouped[
            (
                finding.employee_id,
                finding.code,
                finding.severity,
                finding.message,
                finding.scoring_impact,
            )
        ].append(finding)

    alerts = [
        PerformanceAlert(
            code=code,
            severity=severity,
            message=message,
            employee_id=group_employee_id,
            employee_name=(
                employee_by_id[group_employee_id].employee_name
                if group_employee_id in employee_by_id
                else None
            ),
            team=(
                employee_by_id[group_employee_id].team
                if group_employee_id in employee_by_id
                else None
            ),
            occurrence_count=len(group_findings),
            record_ids=sorted(
                {
                    record_id
                    for finding in group_findings
                    for record_id in finding.record_ids
                }
            ),
            evidence_links=sorted(
                {
                    project_links[record_id]
                    for finding in group_findings
                    for record_id in finding.record_ids
                    if record_id in project_links
                }
            ),
            scoring_impact=scoring_impact,
        )
        for (
            group_employee_id,
            code,
            severity,
            message,
            scoring_impact,
        ), group_findings in grouped.items()
    ]
    return sorted(
        alerts,
        key=lambda alert: (
            severity_order[alert.severity],
            alert.employee_id or "",
            alert.code,
        ),
    )
