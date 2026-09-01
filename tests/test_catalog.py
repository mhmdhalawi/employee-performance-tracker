from unittest import TestCase

from app.schemas.uploads import (
    CalculatorInvocation,
    CatalogTable,
    TableClassification,
    UploadCatalog,
)
from app.services.catalog import validate_classifications


class CalculationPlanValidationTests(TestCase):
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
