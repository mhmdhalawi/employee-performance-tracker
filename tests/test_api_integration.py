from concurrent.futures import ThreadPoolExecutor
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
from app.core.database import database_connection
from app.core.storage import (
    CanonicalRecordWrite,
    complete_submission,
    create_submission,
    fail_submission,
)
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

    def _post_benchmark_tables(self, headers=None, payload=None, plan=None):
        payload = payload or {
            "tables": [
                {"source_name": source_name, "rows": rows}
                for source_name, rows in benchmark_tables().items()
            ]
        }
        with patch.object(
            agent_service,
            "_run_mapping_agent",
            AsyncMock(return_value=plan or benchmark_plan()),
        ):
            return self.client.post(
                "/api/v1/analyze-tables",
                json=payload,
                headers=headers or {},
            )

    def _single_employee_batch(self, suffix: str, business_date: str):
        tables = benchmark_tables()
        rows = {
            "Employees": [tables["Employees"][0]],
            "Targets": [tables["Targets"][0]],
            "Projects": [dict(tables["Projects"][0])],
            "Attendance": [dict(tables["Attendance"][0])],
            "Reports": [dict(tables["Reports"][0])],
            "Leave": [dict(tables["Leave"][0])],
            "Quality": [dict(tables["Quality"][0])],
        }
        rows["Projects"][0].update({
            "record_id": f"OUT-001-{suffix}",
            "assigned_date": business_date,
            "due_date": business_date,
            "completed_date": business_date,
        })
        rows["Attendance"][0].update({
            "record_id": f"ATT-001-{suffix}",
            "occurred_on": business_date,
        })
        rows["Reports"][0].update({
            "record_id": f"SUB-001-{suffix}",
            "due_date": business_date,
            "submitted_date": business_date,
        })
        rows["Leave"][0].update({
            "record_id": f"LEV-001-{suffix}",
            "start_date": business_date,
            "end_date": business_date,
        })
        rows["Quality"][0].update({
            "record_id": f"QLT-001-{suffix}",
            "related_output_id": f"OUT-001-{suffix}",
            "occurred_on": business_date,
        })
        return {
            "tables": [
                {"source_name": source_name, "rows": source_rows}
                for source_name, source_rows in rows.items()
            ]
        }

    def _combined_batch(self, *payloads):
        combined = {
            table["source_name"]: []
            for table in payloads[0]["tables"]
        }
        for payload in payloads:
            for table in payload["tables"]:
                combined[table["source_name"]].extend(table["rows"])
        return {
            "tables": [
                {"source_name": source_name, "rows": rows}
                for source_name, rows in combined.items()
            ]
        }

    def _versioned_batch(self, suffix: str, business_date: str, version: int):
        payload = self._single_employee_batch(suffix, business_date)
        for table in payload["tables"]:
            for row in table["rows"]:
                row["source_version"] = version
        plan = benchmark_plan().model_copy(deep=True)
        for classification in plan.table_classifications:
            for invocation in classification.calculator_invocations:
                invocation.field_bindings["source_version"] = "source_version"
        return payload, plan

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

        self.assertEqual(response.status_code, 201)
        table_body = self.client.get("/api/v1/dashboard").json()
        for field in (
            "results",
            "summary",
            "dataset_overview",
            "available_teams",
            "trends",
        ):
            self.assertEqual(table_body[field], upload_body[field], field)
        self.assertEqual(table_body["included_submission_count"], 1)
        self.assertEqual(len(table_body["mapping_summaries"]), 1)

    def test_json_dashboard_supports_existing_filters(self) -> None:
        submitted = self._post_benchmark_tables()
        response = self.client.get("/api/v1/dashboard?employee_id=EMP-027")

        self.assertEqual(submitted.status_code, 201)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["employee_id"] for item in response.json()["results"]],
            ["EMP-027"],
        )

    def test_json_submission_is_available_as_latest_dashboard(self) -> None:
        submitted = self._post_benchmark_tables()

        self.assertEqual(submitted.status_code, 201)
        self.assertEqual(submitted.json()["status"], "completed")
        dashboard = self.client.get("/api/v1/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json()["summary"]["total_employee_count"], 30)
        self.assertEqual(dashboard.json()["included_submission_count"], 1)

    def test_latest_dashboard_uses_persisted_plan_for_filters(self) -> None:
        submitted = self._post_benchmark_tables()
        self.assertEqual(submitted.status_code, 201)
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

    def test_separate_daily_batches_are_combined_and_recalculated(self) -> None:
        monday = self._single_employee_batch("MON", "2026-06-01")
        tuesday = self._single_employee_batch("TUE", "2026-06-02")

        first = self._post_benchmark_tables(payload=monday)
        monday_dashboard = self.client.get("/api/v1/dashboard").json()
        second = self._post_benchmark_tables(payload=tuesday)
        combined = self.client.get("/api/v1/dashboard").json()

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(monday_dashboard["dataset_overview"]["date_end"], "2026-06-01")
        self.assertEqual(combined["coverage_start"], "2026-06-01")
        self.assertEqual(combined["coverage_end"], "2026-06-02")
        self.assertEqual(combined["included_submission_count"], 2)
        for record_type in (
            "productivity_evidence",
            "attendance_compliance_evidence",
            "submission_compliance_evidence",
            "leave_compliance_evidence",
            "quality_evidence",
        ):
            self.assertEqual(combined["dataset_overview"]["record_counts"][record_type], 2)

    def test_partial_evidence_batch_uses_persisted_foundations(self) -> None:
        complete = self._single_employee_batch("PARTIAL", "2026-06-01")
        first_payload = {
            "tables": [
                table for table in complete["tables"]
                if table["source_name"] != "Quality"
            ]
        }
        second_payload = {
            "tables": [
                table for table in complete["tables"]
                if table["source_name"] == "Quality"
            ]
        }
        full_plan = benchmark_plan()
        first_plan = CalculationPlan(
            selected_tables=[
                source for source in full_plan.selected_tables if source != "Quality"
            ],
            table_classifications=[
                item for item in full_plan.table_classifications
                if item.source_name != "Quality"
            ],
        )
        second_plan = CalculationPlan(
            selected_tables=["Quality"],
            table_classifications=[
                item for item in full_plan.table_classifications
                if item.source_name == "Quality"
            ],
        )

        first = self._post_benchmark_tables(payload=first_payload, plan=first_plan)
        before = self.client.get("/api/v1/dashboard").json()
        second = self._post_benchmark_tables(payload=second_payload, plan=second_plan)
        after = self.client.get("/api/v1/dashboard").json()

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(
            before["dataset_overview"]["record_counts"]["quality_evidence"],
            0,
        )
        self.assertEqual(
            after["dataset_overview"]["record_counts"]["quality_evidence"],
            1,
        )
        self.assertEqual(after["included_submission_count"], 2)
        self.assertEqual(after["summary"]["total_employee_count"], 1)
        self.assertIsNotNone(after["results"][0]["overall_score"])
        self.assertEqual(len(after["mapping_summaries"]), 2)

    def test_overlapping_batch_upserts_existing_ids_once(self) -> None:
        week_one = self._single_employee_batch("W1", "2026-06-01")
        week_two = self._single_employee_batch("W2", "2026-06-08")
        overlap = self._combined_batch(week_one, week_two)

        self._post_benchmark_tables(payload=week_one)
        submitted = self._post_benchmark_tables(payload=overlap)
        dashboard = self.client.get("/api/v1/dashboard").json()

        self.assertEqual(submitted.status_code, 201)
        self.assertEqual(
            dashboard["dataset_overview"]["record_counts"]["attendance_compliance_evidence"],
            2,
        )
        with database_connection() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM canonical_records WHERE record_type = 'attendance'"
            ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_idempotency_key_returns_original_receipt_without_republishing(self) -> None:
        payload = self._single_employee_batch("IDEM", "2026-06-01")
        headers = {"Idempotency-Key": "delivery-2026-06-01"}

        first = self._post_benchmark_tables(headers=headers, payload=payload)
        second = self._post_benchmark_tables(headers=headers, payload=payload)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.json(), first.json())
        with database_connection() as connection:
            submissions = connection.execute(
                "SELECT COUNT(*) FROM submissions"
            ).fetchone()[0]
        self.assertEqual(submissions, 1)

    def test_changed_record_id_replaces_canonical_version(self) -> None:
        original = self._single_employee_batch("COR", "2026-06-01")
        corrected = self._single_employee_batch("COR", "2026-06-01")
        report = next(
            table for table in corrected["tables"] if table["source_name"] == "Reports"
        )["rows"][0]
        report.update({
            "submitted_date": "2026-06-02",
            "outcome": "submitted late",
        })

        self._post_benchmark_tables(payload=original)
        before = self.client.get("/api/v1/dashboard").json()["results"][0]
        self._post_benchmark_tables(payload=corrected)
        after = self.client.get("/api/v1/dashboard").json()["results"][0]

        self.assertGreater(before["compliance_score"], after["compliance_score"])
        with database_connection() as connection:
            count = connection.execute(
                """
                SELECT COUNT(*) FROM canonical_records
                WHERE record_type = 'required_report' AND record_id = 'SUB-001-COR'
                """
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_older_source_version_cannot_overwrite_newer_record(self) -> None:
        newer, plan = self._versioned_batch("VER", "2026-06-01", 2)
        older, _ = self._versioned_batch("VER", "2026-06-01", 1)
        older_report = next(
            table for table in older["tables"] if table["source_name"] == "Reports"
        )["rows"][0]
        older_report.update({
            "submitted_date": "2026-06-02",
            "outcome": "submitted late",
        })

        self._post_benchmark_tables(payload=newer, plan=plan)
        expected = self.client.get("/api/v1/dashboard").json()["results"][0]
        self._post_benchmark_tables(payload=older, plan=plan)
        actual = self.client.get("/api/v1/dashboard").json()["results"][0]

        self.assertEqual(actual["compliance_score"], expected["compliance_score"])
        with database_connection() as connection:
            payload_json = connection.execute(
                """
                SELECT payload_json FROM canonical_records
                WHERE record_type = 'required_report' AND record_id = 'SUB-001-VER'
                """
            ).fetchone()[0]
        self.assertIn('"source_version":2', payload_json)

    def test_same_id_batch_replays_collapse_and_conflicts_do_not_publish(self) -> None:
        exact = self._single_employee_batch("DUP", "2026-06-01")
        reports = next(
            table for table in exact["tables"] if table["source_name"] == "Reports"
        )["rows"]
        reports.append(dict(reports[0]))
        exact_receipt = self._post_benchmark_tables(payload=exact)
        self.assertEqual(exact_receipt.status_code, 201)

        conflicting = self._single_employee_batch("BAD", "2026-06-02")
        conflict_reports = next(
            table
            for table in conflicting["tables"]
            if table["source_name"] == "Reports"
        )["rows"]
        changed = dict(conflict_reports[0])
        changed["submitted_date"] = "2026-06-03"
        conflict_reports.append(changed)
        conflict_receipt = self._post_benchmark_tables(payload=conflicting)
        self.assertEqual(conflict_receipt.status_code, 201)

        with database_connection() as connection:
            audit_rows = connection.execute(
                "SELECT response_json FROM analysis_runs ORDER BY rowid"
            ).fetchall()
            exact_count = connection.execute(
                """
                SELECT COUNT(*) FROM canonical_records
                WHERE record_type = 'required_report' AND record_id = 'SUB-001-DUP'
                """
            ).fetchone()[0]
            conflict_count = connection.execute(
                """
                SELECT COUNT(*) FROM canonical_records
                WHERE record_type = 'required_report' AND record_id = 'SUB-001-BAD'
                """
            ).fetchone()[0]
        self.assertIn("duplicate_canonical_record", audit_rows[0][0])
        self.assertIn("conflicting_canonical_record", audit_rows[1][0])
        self.assertEqual(exact_count, 1)
        self.assertEqual(conflict_count, 0)

    def test_pending_and_failed_submissions_are_not_dashboard_sources(self) -> None:
        self._post_benchmark_tables(
            payload=self._single_employee_batch("OK", "2026-06-01")
        )
        create_submission(
            submission_id="pending-test",
            request_json='{"tables":[]}',
            request_sha256="pending",
            schema_fingerprint="pending",
            table_count=1,
            row_count=1,
        )
        create_submission(
            submission_id="failed-test",
            request_json='{"tables":[]}',
            request_sha256="failed",
            schema_fingerprint="failed",
            table_count=1,
            row_count=1,
        )
        fail_submission("failed-test", "expected test failure")

        dashboard = self.client.get("/api/v1/dashboard").json()

        self.assertEqual(dashboard["included_submission_count"], 1)

    def test_concurrent_upserts_leave_one_canonical_identity(self) -> None:
        for index in (1, 2):
            create_submission(
                submission_id=f"concurrent-{index}",
                request_json='{"tables":[]}',
                request_sha256=f"concurrent-{index}",
                schema_fingerprint="concurrent-schema",
                table_count=1,
                row_count=1,
            )

        record = CanonicalRecordWrite(
            record_type="attendance",
            record_id="ATT-CONCURRENT",
            employee_id="EMP-001",
            period_start="2026-06-01",
            period_end="2026-06-01",
            payload_json='{"record_id":"ATT-CONCURRENT"}',
            source_version=None,
            source_updated_at=None,
        )

        def publish(index: int) -> None:
            complete_submission(
                submission_id=f"concurrent-{index}",
                schema_fingerprint="concurrent-schema",
                calculation_plan_json='{"selected_tables":[],"table_classifications":[]}',
                analysis_id=f"concurrent-analysis-{index}",
                coverage_start="2026-06-01",
                coverage_end="2026-06-01",
                model="test",
                total_tokens=0,
                model_requests=0,
                mapping_cache_hit=True,
                response_json="{}",
                canonical_records=[record],
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(publish, (1, 2)))

        with database_connection() as connection:
            canonical_count = connection.execute(
                """
                SELECT COUNT(*) FROM canonical_records
                WHERE record_type = 'attendance' AND record_id = 'ATT-CONCURRENT'
                """
            ).fetchone()[0]
            raw_count = connection.execute(
                "SELECT COUNT(*) FROM submissions"
            ).fetchone()[0]
            audit_count = connection.execute(
                "SELECT COUNT(*) FROM analysis_runs"
            ).fetchone()[0]
        self.assertEqual(canonical_count, 1)
        self.assertEqual(raw_count, 2)
        self.assertEqual(audit_count, 2)

    def test_mixed_schema_bindings_use_conservative_intersection(self) -> None:
        full = self._single_employee_batch("FULL", "2026-06-01")
        reduced = self._single_employee_batch("RED", "2026-06-02")
        attendance = next(
            table for table in reduced["tables"] if table["source_name"] == "Attendance"
        )["rows"][0]
        for field in ("scheduled_start", "actual_start", "lunch_out", "lunch_in"):
            del attendance[field]
        reduced_plan = benchmark_plan().model_copy(deep=True)
        attendance_plan = next(
            item
            for item in reduced_plan.table_classifications
            if item.source_name == "Attendance"
        )
        for field in ("scheduled_start", "actual_start", "lunch_out", "lunch_in"):
            del attendance_plan.calculator_invocations[0].field_bindings[field]

        self._post_benchmark_tables(payload=full)
        self._post_benchmark_tables(payload=reduced, plan=reduced_plan)
        dashboard = self.client.get("/api/v1/dashboard").json()

        self.assertEqual(len(dashboard["mapping_summaries"]), 2)
        self.assertTrue(
            any("different optional bindings" in item for item in dashboard["limitations"])
        )

    def test_period_presets_are_server_resolved_and_mutually_exclusive(self) -> None:
        first = self._single_employee_batch("START", "2026-05-01")
        latest = self._single_employee_batch("END", "2026-06-30")
        self._post_benchmark_tables(payload=first)
        self._post_benchmark_tables(payload=latest)

        four_weeks = self.client.get("/api/v1/dashboard?period_weeks=4")
        conflict = self.client.get(
            "/api/v1/dashboard?period_weeks=4&start_date=2026-06-01"
        )
        invalid = self.client.get("/api/v1/dashboard?period_weeks=6")

        self.assertEqual(four_weeks.status_code, 200)
        self.assertEqual(four_weeks.json()["applied_filters"]["start_date"], "2026-06-03")
        self.assertEqual(four_weeks.json()["applied_filters"]["end_date"], "2026-06-30")
        self.assertEqual(four_weeks.json()["applied_filters"]["period_weeks"], 4)
        self.assertEqual(conflict.status_code, 400)
        self.assertEqual(invalid.status_code, 400)

    def test_filter_facets_remain_unfiltered(self) -> None:
        self._post_benchmark_tables()

        filtered = self.client.get("/api/v1/dashboard?employee_id=EMP-001").json()

        self.assertEqual(len(filtered["results"]), 1)
        self.assertEqual(len(filtered["available_employees"]), 30)
        self.assertGreater(len(filtered["available_teams"]), 1)

    def test_latest_dashboard_requires_a_completed_submission(self) -> None:
        response = self.client.get("/api/v1/dashboard")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "dashboard_not_found")
        self.assertEqual(
            response.json()["error"]["message"],
            "No completed data submission is available.",
        )

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
