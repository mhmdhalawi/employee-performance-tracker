from dataclasses import dataclass
from typing import Literal, get_args

from pydantic import BaseModel

from app.schemas.performance import (
    AttendanceComplianceEvidence,
    Employee,
    LeaveComplianceEvidence,
    PerformanceTarget,
    QualityEvidence,
    SubmissionComplianceEvidence,
    WorkOutputEvidence,
)

type KpiFamily = Literal["productivity", "compliance", "quality", "shared"]
type TableRole = Literal[
    "productivity",
    "compliance",
    "quality",
    "shared",
    "irrelevant",
]
type CalculatorName = Literal[
    "calculate_productivity",
    "calculate_attendance_compliance",
    "calculate_submission_compliance",
    "calculate_leave_compliance",
    "calculate_quality",
    "load_employees",
    "load_performance_targets",
]


@dataclass(frozen=True, slots=True)
class CalculatorSpec:
    name: CalculatorName
    model: type[BaseModel]
    kpi_family: KpiFamily
    collection_name: str
    record_type: str
    identity_field: str
    start_field: str | None = None
    end_field: str | None = None

    @property
    def required_fields(self) -> list[str]:
        return [
            name
            for name, field in self.model.model_fields.items()
            if field.is_required()
        ]

    @property
    def optional_fields(self) -> list[str]:
        return [
            name
            for name, field in self.model.model_fields.items()
            if not field.is_required()
        ]


# One ordered registry per approved calculator. Every derived view below — the agent-facing
# contract, evidence binding, canonical persistence, and aggregation — reads from this tuple,
# so adding a calculator is a single edit. Order is significant: it fixes the order of the
# contract sent to the model and of canonical record writes.
CALCULATORS: tuple[CalculatorSpec, ...] = (
    CalculatorSpec(
        name="load_employees",
        model=Employee,
        kpi_family="shared",
        collection_name="employees",
        record_type="employee",
        identity_field="employee_id",
    ),
    CalculatorSpec(
        name="load_performance_targets",
        model=PerformanceTarget,
        kpi_family="shared",
        collection_name="performance_targets",
        record_type="performance_target",
        identity_field="employee_id",
    ),
    CalculatorSpec(
        name="calculate_productivity",
        model=WorkOutputEvidence,
        kpi_family="productivity",
        collection_name="work_outputs",
        record_type="work_output",
        identity_field="record_id",
        start_field="assigned_date",
        end_field="assigned_date",
    ),
    CalculatorSpec(
        name="calculate_attendance_compliance",
        model=AttendanceComplianceEvidence,
        kpi_family="compliance",
        collection_name="attendance_events",
        record_type="attendance",
        identity_field="record_id",
        start_field="occurred_on",
        end_field="occurred_on",
    ),
    CalculatorSpec(
        name="calculate_submission_compliance",
        model=SubmissionComplianceEvidence,
        kpi_family="compliance",
        collection_name="submission_events",
        record_type="required_report",
        identity_field="record_id",
        start_field="due_date",
        end_field="due_date",
    ),
    CalculatorSpec(
        name="calculate_leave_compliance",
        model=LeaveComplianceEvidence,
        kpi_family="compliance",
        collection_name="leave_events",
        record_type="leave",
        identity_field="record_id",
        start_field="start_date",
        end_field="end_date",
    ),
    CalculatorSpec(
        name="calculate_quality",
        model=QualityEvidence,
        kpi_family="quality",
        collection_name="quality_events",
        record_type="quality_review",
        identity_field="record_id",
        start_field="occurred_on",
        end_field="occurred_on",
    ),
)

CALCULATOR_BY_NAME: dict[str, CalculatorSpec] = {
    spec.name: spec for spec in CALCULATORS
}
CALCULATOR_BY_RECORD_TYPE: dict[str, CalculatorSpec] = {
    spec.record_type: spec for spec in CALCULATORS
}

# Calculators that supply the employee and target foundations every KPI calculation needs.
FOUNDATION_CALCULATORS: frozenset[str] = frozenset(
    spec.name for spec in CALCULATORS if spec.kpi_family == "shared"
)

# Fails at import if CalculatorName and the registry drift apart.
_declared_names = frozenset(get_args(CalculatorName.__value__))
if _declared_names != frozenset(CALCULATOR_BY_NAME):
    raise RuntimeError(
        "CalculatorName and CALCULATORS must declare the same calculators; "
        f"they differ by {sorted(_declared_names ^ frozenset(CALCULATOR_BY_NAME))}."
    )
