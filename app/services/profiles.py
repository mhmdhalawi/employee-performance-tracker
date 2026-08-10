from dataclasses import dataclass, field

from app.core.errors import UnknownProfileError
from app.schemas.kpi import KpiFamily, MetricDirection


@dataclass(frozen=True)
class MetricDefinition:
    """One canonical metric: where it comes from and how it scores."""

    name: str
    label: str
    family: KpiFamily
    direction: MetricDirection
    target: float
    weight: float
    unit: str | None = None
    aliases: tuple[str, ...] = ()
    description: str = ""

    def accepted_columns(self) -> list[str]:
        return [self.name, *self.aliases]


@dataclass(frozen=True)
class RoleProfile:
    key: str
    label: str
    description: str
    metrics: tuple[MetricDefinition, ...]
    id_aliases: tuple[str, ...] = ("employee_id", "emp_id", "id", "employee", "agent_id")
    name_aliases: tuple[str, ...] = ("employee_name", "name", "full_name", "agent")
    period_aliases: tuple[str, ...] = ("period", "month", "week", "date", "reporting_period")

    def metrics_by_family(self, family: KpiFamily) -> list[MetricDefinition]:
        return [m for m in self.metrics if m.family == family]

    def metric_names(self) -> set[str]:
        return {m.name for m in self.metrics}


# --- Compliance metrics are shared: same company rules apply to every role. ---

_COMPLIANCE_METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        name="attendance_rate",
        label="Attendance rate",
        family="compliance",
        direction="higher_better",
        target=0.98,
        weight=0.4,
        unit="ratio",
        aliases=("attendance", "attendance_%", "presence_rate", "attendance_percentage"),
        description="Share of scheduled working days actually attended.",
    ),
    MetricDefinition(
        name="deadlines_met_rate",
        label="Deadlines met",
        family="compliance",
        direction="higher_better",
        target=0.95,
        weight=0.35,
        unit="ratio",
        aliases=("deadlines_met", "on_time_rate", "sla_met_rate", "on_time_delivery"),
        description="Share of commitments delivered by their due date.",
    ),
    MetricDefinition(
        name="required_submissions_rate",
        label="Required submissions",
        family="compliance",
        direction="higher_better",
        target=1.0,
        weight=0.25,
        unit="ratio",
        aliases=(
            "submissions_rate",
            "timesheets_submitted",
            "reports_submitted_rate",
            "mandatory_submissions",
        ),
        description="Share of mandatory reports/timesheets submitted on time.",
    ),
)


SUPPORT_PROFILE = RoleProfile(
    key="support",
    label="Customer support",
    description="Ticket-driven support roles measured on volume, speed and satisfaction.",
    metrics=(
        MetricDefinition(
            name="tickets_resolved",
            label="Tickets resolved",
            family="productivity",
            direction="higher_better",
            target=120.0,
            weight=0.6,
            unit="tickets",
            aliases=("resolved_tickets", "tickets_closed", "closed_tickets", "tickets"),
            description="Tickets closed in the period.",
        ),
        MetricDefinition(
            name="avg_response_time_minutes",
            label="Average first response time",
            family="productivity",
            direction="lower_better",
            target=15.0,
            weight=0.4,
            unit="minutes",
            aliases=(
                "response_time",
                "avg_response_time",
                "first_response_time",
                "response_time_minutes",
            ),
            description="Mean time to first response.",
        ),
        MetricDefinition(
            name="customer_satisfaction",
            label="Customer satisfaction (CSAT)",
            family="quality",
            direction="higher_better",
            target=0.9,
            weight=0.5,
            unit="ratio",
            aliases=("csat", "satisfaction", "customer_satisfaction_score", "csat_score"),
            description="CSAT as a 0-1 ratio.",
        ),
        MetricDefinition(
            name="reopened_tickets",
            label="Reopened tickets",
            family="quality",
            direction="lower_better",
            target=3.0,
            weight=0.3,
            unit="tickets",
            aliases=("tickets_reopened", "reopens", "reopen_count"),
            description="Tickets reopened after being closed — a rework signal.",
        ),
        MetricDefinition(
            name="escalation_rate",
            label="Escalation rate",
            family="quality",
            direction="lower_better",
            target=0.05,
            weight=0.2,
            unit="ratio",
            aliases=("escalations_rate", "escalated_rate", "escalation_percentage"),
            description="Share of tickets escalated to another team.",
        ),
        *_COMPLIANCE_METRICS,
    ),
)


DEVELOPER_PROFILE = RoleProfile(
    key="developer",
    label="Developer",
    description="Delivery roles measured on shipped work, cycle time and defect rates.",
    metrics=(
        MetricDefinition(
            name="tasks_completed",
            label="Tasks completed",
            family="productivity",
            direction="higher_better",
            target=20.0,
            weight=0.4,
            unit="tasks",
            aliases=(
                "completed_tasks",
                "projects_completed",
                "tickets_completed",
                "issues_closed",
                "stories_completed",
            ),
            description="Units of work delivered in the period.",
        ),
        MetricDefinition(
            name="story_points",
            label="Story points delivered",
            family="productivity",
            direction="higher_better",
            target=40.0,
            weight=0.3,
            unit="points",
            aliases=("points", "story_points_completed", "complexity_points", "velocity"),
            description="Complexity-weighted output.",
        ),
        MetricDefinition(
            name="cycle_time_days",
            label="Cycle time",
            family="productivity",
            direction="lower_better",
            target=3.0,
            weight=0.3,
            unit="days",
            aliases=("cycle_time", "lead_time_days", "avg_cycle_time", "cycle_time_in_days"),
            description="Mean time from start to done.",
        ),
        MetricDefinition(
            name="bugs_reported",
            label="Bugs attributed",
            family="quality",
            direction="lower_better",
            target=2.0,
            weight=0.4,
            unit="bugs",
            aliases=("bugs", "defects", "bug_count", "post_release_bugs"),
            description="Defects traced to work delivered in the period.",
        ),
        MetricDefinition(
            name="rework_rate",
            label="Rework rate",
            family="quality",
            direction="lower_better",
            target=0.1,
            weight=0.35,
            unit="ratio",
            aliases=("rework", "rework_percentage", "reopened_rate", "revert_rate"),
            description="Share of delivered work that had to be redone.",
        ),
        MetricDefinition(
            name="code_review_approval_rate",
            label="Review approval rate",
            family="quality",
            direction="higher_better",
            target=0.9,
            weight=0.25,
            unit="ratio",
            aliases=("review_approval_rate", "pr_approval_rate", "first_pass_approval"),
            description="Share of changes approved without major revision.",
        ),
        *_COMPLIANCE_METRICS,
    ),
)


PROFILES: dict[str, RoleProfile] = {
    SUPPORT_PROFILE.key: SUPPORT_PROFILE,
    DEVELOPER_PROFILE.key: DEVELOPER_PROFILE,
}

DEFAULT_PROFILE_KEY = SUPPORT_PROFILE.key


def get_profile(key: str) -> RoleProfile:
    """Look up a profile by key. Raises UnknownProfileError."""
    profile = PROFILES.get(key.strip().lower())
    if profile is None:
        raise UnknownProfileError(
            f"Unknown profile {key!r}.", {"available": sorted(PROFILES)}
        )
    return profile


def list_profiles() -> list[RoleProfile]:
    return list(PROFILES.values())


def normalize_header(header: str) -> str:
    """Reduce a spreadsheet header to a comparable key.

    ``'Avg. Response Time (minutes)'`` -> ``'avg_response_time_minutes'``.
    """
    cleaned = []
    for char in str(header).strip().lower():
        cleaned.append(char if char.isalnum() or char == "%" else " ")
    parts = "".join(cleaned).split()
    return "_".join(parts)


@dataclass
class ColumnMapping:
    """Result of matching a file's headers against a profile."""

    id_column: str | None = None
    name_column: str | None = None
    period_column: str | None = None
    metric_columns: dict[str, str] = field(default_factory=dict)
    """canonical metric name -> original header in the file."""
    unmapped: list[str] = field(default_factory=list)


def build_column_mapping(headers: list[str], profile: RoleProfile) -> ColumnMapping:
    """Match raw headers to canonical fields for ``profile``.

    First match wins, so a file with both ``tickets`` and ``tickets_closed``
    resolves to whichever appears first — documented rather than silently
    arbitrary. Unrecognized headers are collected and ignored during scoring.
    """
    lookup: dict[str, str] = {}
    for metric in profile.metrics:
        for accepted in metric.accepted_columns():
            lookup.setdefault(normalize_header(accepted), metric.name)

    mapping = ColumnMapping()
    id_keys = {normalize_header(a) for a in profile.id_aliases}
    name_keys = {normalize_header(a) for a in profile.name_aliases}
    period_keys = {normalize_header(a) for a in profile.period_aliases}

    for header in headers:
        key = normalize_header(header)
        if key in id_keys and mapping.id_column is None:
            mapping.id_column = header
        elif key in name_keys and mapping.name_column is None:
            mapping.name_column = header
        elif key in period_keys and mapping.period_column is None:
            mapping.period_column = header
        elif key in lookup and lookup[key] not in mapping.metric_columns:
            mapping.metric_columns[lookup[key]] = header
        else:
            mapping.unmapped.append(header)

    return mapping


def detect_profile(headers: list[str]) -> tuple[RoleProfile, int]:
    """Pick the profile whose metric columns best match ``headers``.

    Returns the profile and how many metric columns it matched. Compliance
    metrics are shared, so they are excluded from the comparison — otherwise
    every profile would tie on an attendance-only file. Ties fall back to
    ``DEFAULT_PROFILE_KEY``.
    """
    best_profile = PROFILES[DEFAULT_PROFILE_KEY]
    best_score = -1

    for profile in list_profiles():
        mapping = build_column_mapping(headers, profile)
        distinctive = {
            name
            for name in mapping.metric_columns
            if not any(name == m.name for m in _COMPLIANCE_METRICS)
        }
        score = len(distinctive)
        if score > best_score:
            best_profile, best_score = profile, score

    return best_profile, max(best_score, 0)
