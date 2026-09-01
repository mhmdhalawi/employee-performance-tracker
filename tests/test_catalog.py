from unittest import TestCase

from app.schemas.uploads import (
    AgentCalculationPlan,
    AgentTableClassification,
    CalculatorInvocation,
    CatalogTable,
    ClassificationValidation,
    TableClassification,
    UploadCatalog,
)
from app.services.catalog import validate_classifications
from app.services.agent import (
    _build_targeted_repair_context,
    _build_workbook_context,
    _expand_agent_plan,
    _mapping_model_settings,
    _merge_agent_plan,
)


class CalculationPlanValidationTests(TestCase):
    def test_mapping_agent_uses_model_default_reasoning_effort(self) -> None:
        self.assertNotIn("openai_reasoning_effort", _mapping_model_settings())

    def test_kpi_plan_requires_employee_and_target_loaders(self) -> None:
        catalog = UploadCatalog(
            file_name="evidence.csv",
            file_type="csv",
            byte_size=1,
            tables=[
                CatalogTable(
                    source_name="Projects",
                    header_row=1,
                    row_count=0,
                    columns=[
                        "record_id",
                        "employee_id",
                        "assigned_date",
                        "due_date",
                        "completion_status",
                        "verification_status",
                    ],
                    rows=[],
                )
            ],
        )
        classifications = [
            TableClassification(
                source_name="Projects",
                kpi_family="productivity",
                calculator_invocations=[
                    CalculatorInvocation(
                        calculator="calculate_productivity",
                        field_bindings={
                            "record_id": "record_id",
                            "employee_id": "employee_id",
                            "assigned_date": "assigned_date",
                            "due_date": "due_date",
                            "completion_status": "completion_status",
                            "verification_status": "verification_status",
                        },
                    )
                ],
                confidence="high",
                rationale="Project evidence is structurally complete.",
            )
        ]

        validations = validate_classifications(catalog, classifications)
        plan_validation = next(
            item for item in validations if item.source_name == "calculation_plan"
        )

        self.assertFalse(plan_validation.valid)
        self.assertEqual(
            plan_validation.missing_required_fields,
            ["load_employees", "load_performance_targets"],
        )

    def test_agent_plan_expansion_derives_non_scoring_fields(self) -> None:
        expanded = _expand_agent_plan(
            AgentCalculationPlan(
                table_classifications=[
                    AgentTableClassification(
                        source_name="Projects",
                        kpi_family="productivity",
                        calculator_invocations=[
                            CalculatorInvocation(
                                calculator="calculate_productivity",
                                field_bindings={"employee_id": "employee_id"},
                            )
                        ],
                        confidence="high",
                    ),
                    AgentTableClassification(
                        source_name="Notes",
                        kpi_family="irrelevant",
                        calculator_invocations=[],
                        confidence="high",
                    ),
                ]
            )
        )

        self.assertEqual(expanded.selected_tables, ["Projects"])
        self.assertEqual(
            expanded.table_classifications[0].calculator_invocations[0].field_bindings,
            {"employee_id": "employee_id"},
        )
        self.assertTrue(expanded.table_classifications[0].rationale)

    def test_mapping_context_uses_signals_without_counts_or_sample_rows(self) -> None:
        upload = UploadCatalog(
            file_name="evidence.csv",
            file_type="csv",
            byte_size=1,
            tables=[
                CatalogTable(
                    source_name="Delivery_Log",
                    header_row=1,
                    row_count=3,
                    columns=["task_ref", "state", "score"],
                    rows=[
                        {"task_ref": "TASK-1", "state": "Completed", "score": 1},
                        {"task_ref": "TASK-2", "state": "In Progress", "score": 0.5},
                        {"task_ref": "TASK-3", "state": "Completed", "score": None},
                    ],
                )
            ],
        )

        context = _build_workbook_context(upload)
        table = context["tables"][0]
        columns = {column["name"]: column for column in table["columns"]}

        self.assertNotIn("sample_rows", table)
        self.assertNotIn("duplicate_row_count", table)
        self.assertEqual(columns["task_ref"]["type"], "text")
        self.assertIn("identifier_name", columns["task_ref"]["signals"])
        self.assertIn("low_cardinality", columns["state"]["signals"])
        self.assertIn("range_0_1", columns["score"]["signals"])
        for column in columns.values():
            self.assertNotIn("missing_count", column)
            self.assertNotIn("unique_count", column)
            self.assertNotIn("examples", column)

    def test_targeted_repair_context_includes_only_safe_categorical_examples(self) -> None:
        upload = UploadCatalog(
            file_name="evidence.csv",
            file_type="csv",
            byte_size=1,
            tables=[
                CatalogTable(
                    source_name="Delivery_Log",
                    header_row=1,
                    row_count=3,
                    columns=["task_ref", "employee_name", "state"],
                    rows=[
                        {
                            "task_ref": "TASK-1",
                            "employee_name": "Employee One",
                            "state": "Completed",
                        },
                        {
                            "task_ref": "TASK-2",
                            "employee_name": "Employee Two",
                            "state": "In Progress",
                        },
                        {
                            "task_ref": "TASK-3",
                            "employee_name": "Employee Three",
                            "state": "Completed",
                        },
                    ],
                )
            ],
        )
        invalid = [
            ClassificationValidation(
                source_name="Delivery_Log",
                kpi_family="productivity",
                valid=False,
                unknown_source_columns=[],
                duplicate_source_columns=[],
                missing_required_fields=["completion_status"],
                invalid_calculators=[],
                message="Missing required field binding.",
            )
        ]

        context = _build_targeted_repair_context(
            upload,
            {item.source_name for item in invalid},
        )
        columns = {
            column["name"]: column
            for column in context["tables"][0]["columns"]
        }

        self.assertEqual(columns["state"]["examples"], ["Completed", "In Progress"])
        self.assertNotIn("examples", columns["task_ref"])
        self.assertNotIn("examples", columns["employee_name"])

    def test_repair_plan_replaces_only_returned_classifications(self) -> None:
        original = AgentCalculationPlan(
            table_classifications=[
                AgentTableClassification(
                    source_name="Projects",
                    kpi_family="unsupported",
                    calculator_invocations=[],
                    confidence="low",
                ),
                AgentTableClassification(
                    source_name="Notes",
                    kpi_family="irrelevant",
                    calculator_invocations=[],
                    confidence="high",
                ),
            ]
        )
        repairs = AgentCalculationPlan(
            table_classifications=[
                AgentTableClassification(
                    source_name="Projects",
                    kpi_family="productivity",
                    calculator_invocations=[
                        CalculatorInvocation(
                            calculator="calculate_productivity",
                            field_bindings={"employee_id": "employee_id"},
                        )
                    ],
                    confidence="high",
                ),
                AgentTableClassification(
                    source_name="Notes",
                    kpi_family="unsupported",
                    calculator_invocations=[],
                    confidence="low",
                ),
            ]
        )

        merged = _merge_agent_plan(original, repairs, {"Projects"})

        self.assertEqual(
            [item.source_name for item in merged.table_classifications],
            ["Projects", "Notes"],
        )
        self.assertEqual(merged.table_classifications[0].kpi_family, "productivity")
        self.assertEqual(merged.table_classifications[1].kpi_family, "irrelevant")
