from unittest import TestCase

from app.services.datasets import build_performance_dataset
from app.services.imports import parse_upload
from app.services.performance import calculate_kpis, summarize_validation, validate_dataset
from tests.benchmark_fixture import benchmark_plan, benchmark_xlsx, load_expected, load_spec


class CedarBenchmarkRegressionTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        catalog = parse_upload("cedar-30-sanitized.xlsx", benchmark_xlsx(), 10_000_000)
        cls.dataset, cls.import_issues = build_performance_dataset(
            catalog, benchmark_plan().table_classifications
        )
        cls.findings = validate_dataset(cls.dataset)
        cls.results = {item.employee_id: item for item in calculate_kpis(
            cls.dataset, validation_findings=cls.findings
        )}
        cls.expected = load_expected()
        cls.spec = load_spec()

    def test_all_30_expected_results_are_reproduced(self) -> None:
        self.assertEqual(len(self.results), 30)
        self.assertEqual(self.import_issues, [])
        tolerance = self.expected["tolerance"]
        for employee_id, result in self.results.items():
            expected = dict(self.expected["default"])
            expected.update(self.expected["overrides"].get(employee_id, {}))
            for field in ("productivity_score", "compliance_score", "quality_score", "data_confidence"):
                self.assertAlmostEqual(getattr(result, field), expected[field], delta=tolerance)
            self.assertEqual(result.overall_score, expected["overall_score"])
            self.assertEqual(result.result_status, expected["result_status"])

    def test_emp_027_through_030_confidence_guardrail(self) -> None:
        for employee_id in self.spec["insufficient_data_ids"]:
            result = self.results[employee_id]
            self.assertEqual(result.data_confidence, 60)
            self.assertIsNone(result.overall_score)
            self.assertIsNone(result.performance_tier)
            self.assertEqual(result.result_status, "Insufficient data")

    def test_duplicate_attendance_is_excluded_and_traceable(self) -> None:
        duplicates = [item for item in self.findings if item.code == "duplicate_attendance"]
        self.assertEqual({item.employee_id for item in duplicates}, set(self.spec["duplicate_attendance_ids"]))
        self.assertEqual(summarize_validation(self.findings).excluded_record_count, 4)
        for finding in duplicates:
            excluded_id = finding.record_ids[1]
            self.assertNotIn(excluded_id, self.results[finding.employee_id].supporting_record_ids)

    def test_emp_027_and_029_are_the_only_documented_parity_exceptions(self) -> None:
        exceptions = self.expected["documented_workbook_exceptions"]
        self.assertEqual(set(exceptions), {"EMP-027", "EMP-029"})
        for employee_id, exception in exceptions.items():
            actual = getattr(self.results[employee_id], exception["field"])
            self.assertEqual(actual, exception["production_expected"])
            self.assertAlmostEqual(
                abs(actual - exception["workbook_expected"]),
                exception["difference"],
                places=4,
            )
