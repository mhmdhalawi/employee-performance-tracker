from io import BytesIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import AsyncMock, patch

import pandas as pd
from fastapi.testclient import TestClient

os.environ["DEBUG"] = "false"

from app.core.config import get_settings
from app.main import app
from app.schemas.uploads import CalculationPlan, CalculatorInvocation, TableClassification
from app.services import agent as agent_service
from tests.benchmark_fixture import benchmark_plan, benchmark_tables, benchmark_xlsx


class AnalyzeApiIntegrationTests(TestCase):
    def setUp(self) -> None:
        agent_service._mapping_cache.clear()
        self._temporary_directory = TemporaryDirectory()
        self._original_database_path = get_settings().database_path
        get_settings().database_path = Path(self._temporary_directory.name) / "tracker.sqlite3"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        get_settings().database_path = self._original_database_path
        self._temporary_directory.cleanup()

    def _post_benchmark(self, query: str = ""):
        with patch.object(agent_service, "_run_mapping_agent", AsyncMock(return_value=benchmark_plan())):
            return self.client.post(
                f"/api/v1/analyze{query}",
                files={"file": ("cedar-30-sanitized.xlsx", benchmark_xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )

    def _post_benchmark_tables(self, query: str = ""):
        payload = {
            "tables": [
                {"source_name": source_name, "rows": rows}
                for source_name, rows in benchmark_tables().items()
            ]
        }
        with patch.object(agent_service, "_run_mapping_agent", AsyncMock(return_value=benchmark_plan())):
            return self.client.post(f"/api/v1/analyze-tables{query}", json=payload)

    def test_full_xlsx_upload_runs_without_an_api_key(self) -> None:
        response = self._post_benchmark()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["total_employee_count"], 30)
        self.assertEqual(body["summary"]["insufficient_data_employee_ids"], ["EMP-027", "EMP-028", "EMP-029", "EMP-030"])
        self.assertEqual(body["validation_summary"]["excluded_record_count"], 4)
        self.assertEqual(body["model_requests"], 0)
        self.assertNotIn("model_usage", body)
        self.assertNotIn("timings", body)

    def test_json_tables_match_the_upload_analysis(self) -> None:
        upload_body = self._post_benchmark().json()
        agent_service._mapping_cache.clear()
        response = self._post_benchmark_tables()

        self.assertEqual(response.status_code, 200)
        table_body = response.json()
        for field in (
            "results",
            "summary",
            "dataset_overview",
            "available_teams",
            "trends",
            "alerts",
            "import_issues",
            "validation_summary",
            "global_validation_findings",
            "selected_tables",
            "table_classifications",
            "limitations",
        ):
            self.assertEqual(table_body[field], upload_body[field], field)
        self.assertNotIn("file_name", table_body)
        self.assertNotIn("file_type", table_body)
        self.assertNotIn("byte_size", table_body)

    def test_json_tables_support_existing_filters(self) -> None:
        response = self._post_benchmark_tables("?employee_id=EMP-027")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["employee_id"] for item in response.json()["results"]],
            ["EMP-027"],
        )

    def test_json_submission_is_available_as_latest_dashboard(self) -> None:
        submitted = self._post_benchmark_tables()

        self.assertEqual(submitted.status_code, 200)
        dashboard = self.client.get("/api/v1/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        for field in (
            "results",
            "summary",
            "dataset_overview",
            "available_teams",
            "trends",
            "alerts",
            "table_classifications",
            "limitations",
        ):
            self.assertEqual(dashboard.json()[field], submitted.json()[field], field)
        self.assertNotEqual(
            dashboard.json()["analysis_id"],
            submitted.json()["analysis_id"],
        )

    def test_latest_dashboard_uses_persisted_plan_for_filters(self) -> None:
        submitted = self._post_benchmark_tables()
        self.assertEqual(submitted.status_code, 200)
        agent_service._mapping_cache.clear()

        mapping_agent = AsyncMock(side_effect=AssertionError("mapping agent should not run"))
        with patch.object(agent_service, "_run_mapping_agent", mapping_agent):
            filtered = self.client.get(
                "/api/v1/dashboard?start_date=2026-06-01&end_date=2026-06-05"
            )

        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(
            filtered.json()["applied_filters"]["start_date"],
            "2026-06-01",
        )
        employee = self.client.get("/api/v1/dashboard?employee_id=EMP-027")
        self.assertEqual(employee.status_code, 200)
        self.assertEqual(
            [item["employee_id"] for item in employee.json()["results"]],
            ["EMP-027"],
        )
        team = self.client.get("/api/v1/dashboard?team=Automation")
        self.assertEqual(team.status_code, 200)
        self.assertTrue(
            all(item["team"] == "Automation" for item in team.json()["results"])
        )
        mapping_agent.assert_not_awaited()

    def test_latest_dashboard_requires_a_completed_submission(self) -> None:
        response = self.client.get("/api/v1/dashboard")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "dashboard_not_found")

    def test_invalid_json_table_shapes_return_422(self) -> None:
        duplicate_names = self.client.post(
            "/api/v1/analyze-tables",
            json={
                "tables": [
                    {"source_name": "Employees", "rows": [{"employee_id": "1"}]},
                    {"source_name": "employees", "rows": [{"employee_id": "2"}]},
                ]
            },
        )
        reserved_column = self.client.post(
            "/api/v1/analyze-tables",
            json={
                "tables": [
                    {
                        "source_name": "Employees",
                        "rows": [{"employee_id": "1", "_source_row": 99}],
                    }
                ]
            },
        )
        nested_cell = self.client.post(
            "/api/v1/analyze-tables",
            json={
                "tables": [
                    {
                        "source_name": "Employees",
                        "rows": [{"employee_id": {"nested": "value"}}],
                    }
                ]
            },
        )

        self.assertEqual(duplicate_names.status_code, 422)
        self.assertEqual(reserved_column.status_code, 422)
        self.assertEqual(nested_cell.status_code, 422)

    def test_employee_team_and_period_filters(self) -> None:
        employee = self._post_benchmark("?employee_id=EMP-027").json()
        self.assertEqual([item["employee_id"] for item in employee["results"]], ["EMP-027"])
        team = self._post_benchmark("?team=Automation").json()
        self.assertEqual(len(team["results"]), 10)
        self.assertTrue(all(item["team"] == "Automation" for item in team["results"]))
        period = self._post_benchmark("?start_date=2026-06-01&end_date=2026-06-05").json()
        self.assertEqual(period["applied_filters"]["start_date"], "2026-06-01")
        self.assertEqual(period["applied_filters"]["end_date"], "2026-06-05")

    def test_csv_upload_is_supported(self) -> None:
        rows = benchmark_tables()["Employees"][:2]
        for row in rows:
            row.update({"target_outputs_90d": 1, "target_avg_effort_hours": 8, "minimum_confidence": 0.7})
        content = pd.DataFrame(rows).to_csv(index=False).encode()
        columns = list(rows[0])
        plan = CalculationPlan(selected_tables=["upload"], table_classifications=[
            TableClassification(source_name="upload", kpi_family="shared", calculator_invocations=[
                CalculatorInvocation(calculator="load_employees", field_bindings={key: key for key in ("employee_id", "employee_name", "team", "role")}),
                CalculatorInvocation(calculator="load_performance_targets", field_bindings={key: key for key in ("employee_id", "target_outputs_90d", "target_avg_effort_hours", "minimum_confidence")}),
            ], confidence="high", rationale="Deterministic CSV integration binding.")
        ])
        with patch.object(agent_service, "_run_mapping_agent", AsyncMock(return_value=plan)):
            response = self.client.post("/api/v1/analyze", files={"file": ("employees.csv", content, "text/csv")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["file_type"], "csv")
        self.assertEqual(len(response.json()["results"]), 2)
        self.assertEqual(set(columns), set(rows[0]))

    def test_invalid_rows_return_200_with_import_findings(self) -> None:
        tables = benchmark_tables()
        tables["Projects"][0]["actual_effort_hours"] = "not-a-number"
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for name, rows in tables.items():
                pd.DataFrame(rows).to_excel(writer, sheet_name=name, index=False)
        with patch.object(agent_service, "_run_mapping_agent", AsyncMock(return_value=benchmark_plan())):
            response = self.client.post("/api/v1/analyze", files={"file": ("invalid-row.xlsx", output.getvalue())})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(item["code"] == "invalid_row" for item in response.json()["import_issues"]))

    def test_unusable_uploads_and_invalid_filters_return_errors(self) -> None:
        wrong_type = self.client.post("/api/v1/analyze", files={"file": ("data.txt", b"a,b\n1,2")})
        self.assertEqual(wrong_type.status_code, 415)
        malformed = self.client.post("/api/v1/analyze", files={"file": ("data.xlsx", b"not an xlsx")})
        self.assertEqual(malformed.status_code, 422)
        reversed_period = self._post_benchmark("?start_date=2026-08-22&end_date=2026-05-25")
        self.assertEqual(reversed_period.status_code, 400)
        unknown_team = self._post_benchmark("?team=Unknown")
        self.assertEqual(unknown_team.status_code, 400)

    def test_oversized_upload_returns_413(self) -> None:
        maximum = get_settings().upload_max_bytes
        response = self.client.post("/api/v1/analyze", files={"file": ("large.csv", b"x" * (maximum + 1))})
        self.assertEqual(response.status_code, 413)
