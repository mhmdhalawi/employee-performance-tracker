import json
from io import BytesIO
from pathlib import Path

import pandas as pd

from app.schemas.uploads import CalculationPlan, CalculatorInvocation, TableClassification


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def load_spec() -> dict[str, object]:
    return json.loads((FIXTURE_DIR / "cedar_30_sanitized.json").read_text())


def load_expected() -> dict[str, object]:
    return json.loads((FIXTURE_DIR / "cedar_30_expected.json").read_text())


def benchmark_tables() -> dict[str, list[dict[str, object]]]:
    spec = load_spec()
    employees = spec["employees"]
    insufficient = set(spec["insufficient_data_ids"])
    duplicates = set(spec["duplicate_attendance_ids"])
    tables: dict[str, list[dict[str, object]]] = {
        "Employees": [], "Targets": [], "Projects": [], "Attendance": [],
        "Reports": [], "Leave": [], "Quality": [],
    }
    for index, item in enumerate(employees, start=1):
        employee_id = item["employee_id"]
        tables["Employees"].append({"employee_id": employee_id, "employee_name": f"Sanitized Employee {index:02d}", "team": item["team"], "role": "Analyst"})
        tables["Targets"].append({"employee_id": employee_id, "target_outputs_90d": 1, "target_avg_effort_hours": 8, "minimum_confidence": 0.7})
        tables["Projects"].append({"record_id": f"OUT-{index:03d}", "employee_id": employee_id, "assigned_date": "2026-06-01", "due_date": "2026-06-02", "completed_date": "2026-06-02", "completion_status": "completed on time", "actual_effort_hours": 8, "verification_status": "verified", "evidence_link": f"https://example.invalid/evidence/{index:03d}"})
        for day in range(1, 6):
            tables["Attendance"].append({"record_id": f"ATT-{index:03d}-{day}", "employee_id": employee_id, "occurred_on": f"2026-06-{day:02d}", "outcome": "on time", "record_status": "complete", "scheduled_start": "09:00", "actual_start": "09:00", "lunch_out": "12:00", "lunch_in": "13:00", "scheduled_end": "17:00", "actual_end": None if employee_id in insufficient and day <= 2 else "17:00", "confidence_score": 1})
        if employee_id in duplicates:
            duplicate = dict(tables["Attendance"][-1])
            duplicate["record_id"] = f"ATT-{index:03d}-DUP"
            tables["Attendance"].append(duplicate)
        tables["Reports"].append({"record_id": f"SUB-{index:03d}", "employee_id": employee_id, "due_date": "2026-06-05", "submitted_date": "2026-06-05", "outcome": "submitted on time", "completeness_ratio": 1, "verification_status": "verified"})
        tables["Leave"].append({"record_id": f"LEV-{index:03d}", "employee_id": employee_id, "category": "annual leave", "start_date": "2026-07-01", "end_date": "2026-07-01", "outcome": "approved", "documentation_complete": True})
        tables["Quality"].append({"record_id": f"QLT-{index:03d}", "related_output_id": f"OUT-{index:03d}", "employee_id": employee_id, "occurred_on": "2026-06-02", "accuracy_ratio": 1, "first_pass_approved": True, "rework_hours": 0, "verification_status": "verified"})
    return tables


def benchmark_xlsx() -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, rows in benchmark_tables().items():
            pd.DataFrame(rows).to_excel(writer, sheet_name=name, index=False)
    return output.getvalue()


def benchmark_plan() -> CalculationPlan:
    bindings = {
        "Employees": ("shared", "load_employees"), "Targets": ("shared", "load_performance_targets"),
        "Projects": ("productivity", "calculate_productivity"), "Attendance": ("compliance", "calculate_attendance_compliance"),
        "Reports": ("compliance", "calculate_submission_compliance"), "Leave": ("compliance", "calculate_leave_compliance"),
        "Quality": ("quality", "calculate_quality"),
    }
    tables = benchmark_tables()
    classifications = []
    for source, (family, calculator) in bindings.items():
        columns = list(tables[source][0])
        classifications.append(TableClassification(source_name=source, kpi_family=family, calculator_invocations=[CalculatorInvocation(calculator=calculator, field_bindings={column: column for column in columns})], confidence="high", rationale="Deterministic sanitized benchmark binding."))
    return CalculationPlan(selected_tables=list(bindings), table_classifications=classifications)
