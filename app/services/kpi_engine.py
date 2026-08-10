from app.schemas.common import NormalizedRecord
from app.schemas.kpi import (
    EmployeeKpiResult,
    KpiComponent,
    KpiFamily,
    KpiFamilyScore,
)
from app.services.profiles import ColumnMapping, MetricDefinition, RoleProfile
from app.utils.numbers import normalize_metric, round_score, safe_div

FAMILIES: tuple[KpiFamily, ...] = ("productivity", "quality", "compliance")

# Families are weighted equally for the MVP. Make this configurable per customer
# only when a customer actually asks for it.
FAMILY_WEIGHTS: dict[KpiFamily, float] = {
    "productivity": 1 / 3,
    "quality": 1 / 3,
    "compliance": 1 / 3,
}


def _build_component(
    definition: MetricDefinition,
    record: NormalizedRecord,
    mapping: ColumnMapping | None,
) -> KpiComponent:
    source_field = mapping.metric_columns.get(definition.name) if mapping else None
    value = record.metrics.get(definition.name)

    if value is None:
        return KpiComponent(
            metric=definition.name,
            label=definition.label,
            source_field=source_field,
            available=False,
            raw_value=None,
            unit=definition.unit,
            target=definition.target,
            direction=definition.direction,
            normalized_score=None,
            weight=definition.weight,
            note="Not present in the source data; excluded from the score.",
        )

    return KpiComponent(
        metric=definition.name,
        label=definition.label,
        source_field=source_field,
        available=True,
        raw_value=value,
        unit=definition.unit,
        target=definition.target,
        direction=definition.direction,
        normalized_score=normalize_metric(value, definition.target, definition.direction),
        weight=definition.weight,
    )


def score_family(
    family: KpiFamily,
    record: NormalizedRecord,
    profile: RoleProfile,
    mapping: ColumnMapping | None = None,
) -> KpiFamilyScore:
    """Score one KPI family as a weighted mean of its available metrics.

    Missing metrics are reported, not guessed: they are excluded and the
    remaining weights are renormalized so a partially populated file still
    yields a meaningful score. With no available metrics the score is ``None``
    with a reason — never ``0.0``, which would read as "performed badly".
    """
    definitions = profile.metrics_by_family(family)
    components = [_build_component(d, record, mapping) for d in definitions]

    available = [c for c in components if c.available]
    missing = [c.metric for c in components if not c.available]

    if not available:
        return KpiFamilyScore(
            family=family,
            score=None,
            reason=(
                "No metrics for this family were present in the source data."
                if definitions
                else f"Profile {profile.key!r} defines no {family} metrics."
            ),
            components=components,
            missing_metrics=missing,
        )

    total_weight = sum(c.weight for c in available)
    score = 0.0
    for component in available:
        component.effective_weight = round(safe_div(component.weight, total_weight), 6)
        component.contribution = round_score(
            (component.normalized_score or 0.0) * component.effective_weight
        )
        score += (component.normalized_score or 0.0) * component.effective_weight

    return KpiFamilyScore(
        family=family,
        score=round_score(score),
        reason=(
            f"Computed from {len(available)} of {len(definitions)} metrics; "
            f"weights renormalized over available metrics."
            if missing
            else None
        ),
        components=components,
        missing_metrics=missing,
    )


def calculate_employee_kpis(
    record: NormalizedRecord,
    profile: RoleProfile,
    mapping: ColumnMapping | None = None,
) -> EmployeeKpiResult:
    """Score all three families for one normalized record."""
    families = {
        family: score_family(family, record, profile, mapping) for family in FAMILIES
    }

    scored = [(f, s) for f, s in families.items() if s.score is not None]
    if scored:
        weight_total = sum(FAMILY_WEIGHTS[f] for f, _ in scored)
        overall = round_score(
            sum((s.score or 0.0) * FAMILY_WEIGHTS[f] for f, s in scored) / weight_total
        )
    else:
        overall = None

    return EmployeeKpiResult(
        employee_id=record.employee_id,
        employee_name=record.employee_name,
        profile=profile.key,
        period=record.period,
        overall_score=overall,
        families=families,
        source_row=record.source_row,
    )


def calculate_batch_kpis(
    records: list[NormalizedRecord],
    profile: RoleProfile,
    mapping: ColumnMapping | None = None,
) -> list[EmployeeKpiResult]:
    return [calculate_employee_kpis(r, profile, mapping) for r in records]
