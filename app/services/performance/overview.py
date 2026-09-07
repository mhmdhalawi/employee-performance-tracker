from app.schemas.performance import DatasetOverview, PerformanceEvidenceDataset


def inspect_dataset(dataset: PerformanceEvidenceDataset) -> DatasetOverview:
    """Return the available population, coverage period, and source record counts."""
    dates = [
        *[record.assigned_date for record in dataset.work_outputs],
        *[record.occurred_on for record in dataset.attendance_events],
        *[record.due_date for record in dataset.submission_events],
        *[record.occurred_on for record in dataset.quality_events],
    ]
    return DatasetOverview(
        employee_count=len(dataset.employees),
        date_start=min(dates) if dates else None,
        date_end=max(dates) if dates else None,
        record_counts={
            "productivity_evidence": len(dataset.work_outputs),
            "attendance_compliance_evidence": len(dataset.attendance_events),
            "submission_compliance_evidence": len(dataset.submission_events),
            "leave_compliance_evidence": len(dataset.leave_events),
            "quality_evidence": len(dataset.quality_events),
        },
        teams=sorted(
            {employee.team for employee in dataset.employees if employee.team}
        ),
    )

