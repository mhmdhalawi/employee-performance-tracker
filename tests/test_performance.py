from datetime import date
from unittest import TestCase

from app.schemas.performance import (
    AttendanceComplianceEvidence,
    Employee,
    LeaveComplianceEvidence,
    PerformanceEvidenceDataset,
    PerformanceTarget,
    QualityEvidence,
    SubmissionComplianceEvidence,
    WorkOutputEvidence,
)
from app.services.performance import (
    build_performance_alerts,
    calculate_kpis,
    get_supporting_evidence,
    validate_dataset,
)


class PerformanceQaTests(TestCase):
    def test_perfect_evidence_calculates_expected_scores(self) -> None:
        result = calculate_kpis(_dataset())[0]

        self.assertEqual(result.productivity_score, 100)
        self.assertEqual(result.compliance_score, 100)
        self.assertEqual(result.quality_score, 100)
        self.assertEqual(result.data_confidence, 100)
        self.assertEqual(result.overall_score, 100)
        self.assertEqual(result.result_status, "Top performer")

    def test_duplicate_attendance_is_flagged_excluded_and_traceable(self) -> None:
        dataset = _dataset()
        dataset.attendance_events.append(
            dataset.attendance_events[0].model_copy(
                update={"record_id": "ATT-002", "outcome": "late"}
            )
        )
        findings = validate_dataset(dataset)
        duplicate = next(item for item in findings if item.code == "duplicate_attendance")
        result = calculate_kpis(dataset, validation_findings=findings)[0]
        alerts = build_performance_alerts(
            dataset,
            findings,
            {result.employee_id},
            set(result.supporting_record_ids),
        )

        self.assertEqual(duplicate.record_ids, ["ATT-001", "ATT-002"])
        self.assertEqual(result.compliance_score, 100)
        self.assertNotIn("ATT-002", result.supporting_record_ids)
        self.assertTrue(any(alert.record_ids == ["ATT-001", "ATT-002"] for alert in alerts))

    def test_approved_leave_is_neutral(self) -> None:
        dataset = _dataset()
        dataset.attendance_events[0] = dataset.attendance_events[0].model_copy(
            update={"outcome": "annual leave", "actual_end": None}
        )

        result = calculate_kpis(dataset)[0]

        self.assertEqual(result.compliance_score, 100)

    def test_missing_exit_is_reported_with_record_id(self) -> None:
        dataset = _dataset()
        dataset.attendance_events[0] = dataset.attendance_events[0].model_copy(
            update={"actual_end": None}
        )

        finding = next(
            item for item in validate_dataset(dataset) if item.code == "missing_actual_end"
        )

        self.assertEqual(finding.record_ids, ["ATT-001"])
        self.assertEqual(finding.scoring_impact, "lowers_confidence")

    def test_late_and_missing_submissions_reduce_compliance(self) -> None:
        late = _dataset()
        late.submission_events[0] = late.submission_events[0].model_copy(
            update={"submitted_date": date(2026, 6, 3), "outcome": "submitted late"}
        )
        missing = _dataset()
        missing.submission_events[0] = missing.submission_events[0].model_copy(
            update={"submitted_date": None, "outcome": "missing"}
        )

        self.assertEqual(calculate_kpis(late)[0].compliance_score, 65)
        self.assertEqual(calculate_kpis(missing)[0].compliance_score, 65)
        self.assertTrue(
            any(item.code == "missing_submission" for item in validate_dataset(missing))
        )

    def test_overdue_work_and_low_quality_are_reported(self) -> None:
        dataset = _dataset()
        dataset.work_outputs[0] = dataset.work_outputs[0].model_copy(
            update={"completion_status": "overdue", "completed_date": None}
        )
        dataset.quality_events[0] = dataset.quality_events[0].model_copy(
            update={"accuracy_ratio": 0.50, "first_pass_approved": False, "rework_hours": 8}
        )
        findings = validate_dataset(dataset)
        result = calculate_kpis(dataset, validation_findings=findings)[0]

        self.assertTrue(any(item.code == "overdue_work_output" for item in findings))
        low_accuracy = next(item for item in findings if item.code == "low_accuracy")
        self.assertIn("coaching", low_accuracy.message.casefold())
        self.assertEqual(low_accuracy.record_ids, ["QLT-001"])
        self.assertEqual(result.quality_score, 35.4)

    def test_unverified_required_evidence_gates_overall_score(self) -> None:
        dataset = _dataset()
        dataset.work_outputs[0] = dataset.work_outputs[0].model_copy(
            update={"verification_status": "missing"}
        )

        result = calculate_kpis(dataset)[0]

        self.assertEqual(result.data_confidence, 0)
        self.assertIsNone(result.overall_score)
        self.assertIsNone(result.performance_tier)
        self.assertEqual(result.result_status, "Insufficient data")

    def test_team_filter_and_supporting_evidence(self) -> None:
        dataset = _dataset()
        second = _dataset(employee_id="EMP-002", team="Operations", suffix="2")
        dataset.employees.extend(second.employees)
        dataset.performance_targets.extend(second.performance_targets)
        dataset.work_outputs.extend(second.work_outputs)
        dataset.attendance_events.extend(second.attendance_events)
        dataset.submission_events.extend(second.submission_events)
        dataset.leave_events.extend(second.leave_events)
        dataset.quality_events.extend(second.quality_events)

        results = calculate_kpis(dataset, team="Operations")
        evidence = get_supporting_evidence(dataset, "EMP-002")

        self.assertEqual([item.employee_id for item in results], ["EMP-002"])
        self.assertEqual(
            set(evidence.record_ids),
            {"OUT-2", "ATT-2", "SUB-2", "QLT-2"},
        )


def _dataset(
    employee_id: str = "EMP-001",
    team: str = "AI Automation",
    suffix: str = "001",
) -> PerformanceEvidenceDataset:
    return PerformanceEvidenceDataset(
        employees=[
            Employee(employee_id=employee_id, employee_name="Test Employee", team=team)
        ],
        performance_targets=[
            PerformanceTarget(
                employee_id=employee_id,
                target_outputs_90d=1,
                target_avg_effort_hours=8,
                minimum_confidence=0.70,
            )
        ],
        work_outputs=[
            WorkOutputEvidence(
                record_id=f"OUT-{suffix}",
                employee_id=employee_id,
                assigned_date=date(2026, 6, 1),
                due_date=date(2026, 6, 2),
                completed_date=date(2026, 6, 2),
                completion_status="completed on time",
                actual_effort_hours=8,
                verification_status="verified",
                evidence_link=f"https://example.com/{suffix}",
            )
        ],
        attendance_events=[
            AttendanceComplianceEvidence(
                record_id=f"ATT-{suffix}",
                employee_id=employee_id,
                occurred_on=date(2026, 6, 1),
                outcome="on time",
                record_status="complete",
                actual_end="17:00",
                confidence_score=1,
            )
        ],
        submission_events=[
            SubmissionComplianceEvidence(
                record_id=f"SUB-{suffix}",
                employee_id=employee_id,
                due_date=date(2026, 6, 2),
                submitted_date=date(2026, 6, 2),
                outcome="submitted on time",
                completeness_ratio=1,
                verification_status="verified",
            )
        ],
        leave_events=[
            LeaveComplianceEvidence(
                record_id=f"LEV-{suffix}",
                employee_id=employee_id,
                category="annual leave",
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 1),
                outcome="approved",
                documentation_complete=True,
            )
        ],
        quality_events=[
            QualityEvidence(
                record_id=f"QLT-{suffix}",
                related_output_id=f"OUT-{suffix}",
                employee_id=employee_id,
                occurred_on=date(2026, 6, 2),
                accuracy_ratio=1,
                first_pass_approved=True,
                rework_hours=0,
                verification_status="verified",
            )
        ],
        mapped_fields={"attendance_events": {"actual_end"}},
    )
