from app.schemas.performance import ValidationFinding

_ACTIONS: dict[str, tuple[str, str]] = {
    "overdue_work_output": ("performance_alert", "Review the overdue work and agree on a completion plan."),
    "late_submission": ("performance_alert", "Review the report deadline and follow up on the delay."),
    "low_accuracy": ("performance_alert", "Review the quality result and agree on a quality improvement plan."),
    "duplicate_employee_id": ("data_issue", "Resolve the duplicate employee ID in the source data."),
    "duplicate_record_id": ("data_issue", "Give each distinct source record a unique ID."),
    "missing_performance_target": ("data_issue", "Provide the employee's KPI target before assessing overall performance."),
    "duplicate_attendance": ("data_issue", "Review the same-day attendance records and correct the duplicate."),
    "missing_productivity_evidence": ("data_issue", "Verify the work evidence in the source system."),
    "missing_actual_effort": ("data_issue", "Provide the actual hours worked for this completed work."),
    "missing_submission": ("data_issue", "Confirm whether the report was submitted and provide its submission date."),
    "missing_submission_evidence": ("data_issue", "Verify the report submission evidence."),
    "incomplete_sick_leave_documentation": ("data_issue", "Complete or confirm the required sick-leave documentation."),
    "orphan_quality_evidence": ("data_issue", "Link the quality review to an existing work record."),
    "missing_quality_evidence": ("data_issue", "Verify the quality-review evidence."),
    "orphan_record": ("data_issue", "Add or correct the referenced employee record."),
    "conflicting_canonical_record": ("data_issue", "Resolve the conflicting rows before resubmitting this record ID."),
    "duplicate_canonical_record": ("data_issue", "Review the repeated row and remove redundant source data."),
    "duplicate_record_content": ("data_issue", "Review the identical records and confirm whether both events occurred."),
}


def describe_finding(finding: ValidationFinding) -> ValidationFinding:
    if finding.code.startswith("missing_") and finding.source_type == "attendance":
        return finding.model_copy(update={
            "category": "data_issue",
            "action": "Provide or correct the missing attendance time in the source record.",
        })
    category, action = _ACTIONS.get(
        finding.code,
        ("data_issue", "Review and correct the source evidence."),
    )
    return finding.model_copy(update={"category": category, "action": action})
