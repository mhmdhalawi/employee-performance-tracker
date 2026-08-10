import json
from dataclasses import dataclass

from pydantic_ai import (
    Agent,
    ModelHTTPError,
    ModelRetry,
    RunContext,
    UnexpectedModelBehavior,
)
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.core.config import get_settings
from app.core.errors import AIMappingError
from app.core.openai_client import get_openai_client
from app.schemas.mapping import AgentMappingProposal, ColumnPreview
from app.services.profiles import PROFILES, MetricDefinition, get_profile, list_profiles
from app.utils.numbers import coerce_float, normalize_metric

INSTRUCTIONS = """\
You map the columns of an uploaded employee-performance spreadsheet onto the canonical metrics
this backend already knows how to score.

You decide *what the data means*. You do not decide what good performance is, and you never
produce a score: targets, directions and weights are fixed by the backend, and all arithmetic
happens in tools.

Process:
1. Call `list_metrics` for each plausible profile to see the metric catalogue.
2. Call `inspect_column` on any column whose meaning is unclear from its name. Units and value
   ranges are strong evidence: a column of values between 0 and 1 is a ratio, not a count.
3. Call `check_mapping` before committing a non-obvious mapping. It scores real sample values
   against the metric's target. Scores that are almost all 0 or almost all 100 usually mean the
   column is the wrong scale or the wrong metric.
4. Return the profile that fits best and one mapping per column you are confident about.

Hard rules:
- Only use metric names returned by `list_metrics`. Never invent a metric name.
- Map each metric at most once, and each column at most once.
- If a column is ambiguous, leave it in `unmapped_columns`. An omitted column is harmless; a
  wrong mapping corrupts someone's performance score.
- Set `confidence` honestly. Use below 0.6 when you are guessing from the column name alone.
- Identify the employee identifier column, and the name/period columns if present.
"""


@dataclass
class MappingDeps:
    previews: dict[str, ColumnPreview]
    candidate_columns: list[str]
    profile_hint: str | None


mapping_agent = Agent(
    model=None,
    deps_type=MappingDeps,
    output_type=AgentMappingProposal,
    instructions=INSTRUCTIONS,
    retries=2,
)


@mapping_agent.instructions
def _describe_file(ctx: RunContext[MappingDeps]) -> str:
    columns = [
        ctx.deps.previews[c].model_dump(exclude_none=True)
        for c in ctx.deps.candidate_columns
        if c in ctx.deps.previews
    ]
    hint = ctx.deps.profile_hint or "unknown"
    return (
        f"Available profiles: {', '.join(sorted(PROFILES))}.\n"
        f"Profile suggested by header matching (may be wrong): {hint}.\n"
        f"Columns you must classify:\n{json.dumps(columns, indent=2, ensure_ascii=False)}"
    )


def _metric_payload(metric: MetricDefinition) -> dict:
    return {
        "metric": metric.name,
        "label": metric.label,
        "family": metric.family,
        "unit": metric.unit,
        "better_when": "higher" if metric.direction == "higher_better" else "lower",
        "target": metric.target,
        "description": metric.description,
        "known_column_spellings": metric.accepted_columns(),
    }


def _find_metric(name: str) -> MetricDefinition | None:
    for profile in list_profiles():
        for metric in profile.metrics:
            if metric.name == name:
                return metric
    return None


@mapping_agent.tool
async def list_metrics(ctx: RunContext[MappingDeps], profile: str) -> list[dict]:
    """List every canonical metric a profile can score, with its unit and target.

    Args:
        profile: Profile key, one of the available profiles.
    """
    try:
        role = get_profile(profile)
    except Exception:
        raise ModelRetry(
            f"Unknown profile {profile!r}. Available: {', '.join(sorted(PROFILES))}."
        ) from None
    return [_metric_payload(m) for m in role.metrics]


@mapping_agent.tool
async def inspect_column(ctx: RunContext[MappingDeps], column: str) -> dict:
    """Show sample values and numeric range for one column of the uploaded file.

    Args:
        column: Exact column header as it appears in the file.
    """
    preview = ctx.deps.previews.get(column)
    if preview is None:
        raise ModelRetry(
            f"No column named {column!r}. Columns: {', '.join(ctx.deps.candidate_columns)}."
        )
    return preview.model_dump(exclude_none=True)


@mapping_agent.tool
async def check_mapping(ctx: RunContext[MappingDeps], column: str, metric: str) -> dict:
    """Score a column's real sample values against a metric's target, to test a mapping.

    Uses the same deterministic scoring the backend applies to the final results, so the output
    tells you whether the column is on the right scale for that metric.

    Args:
        column: Exact column header as it appears in the file.
        metric: Canonical metric name from `list_metrics`.
    """
    preview = ctx.deps.previews.get(column)
    if preview is None:
        raise ModelRetry(f"No column named {column!r}.")

    definition = _find_metric(metric)
    if definition is None:
        raise ModelRetry(f"No metric named {metric!r}. Call list_metrics first.")

    scored: list[dict] = []
    for raw in preview.sample_values:
        value = coerce_float(raw)
        if value is None:
            continue
        scored.append(
            {
                "value": value,
                "score": normalize_metric(value, definition.target, definition.direction),
            }
        )

    if not scored:
        return {
            "metric": metric,
            "column": column,
            "verdict": "no numeric sample values; this column cannot feed a metric",
        }

    scores = [s["score"] for s in scored]
    mean = round(sum(scores) / len(scores), 2)
    # A near-zero mean usually means the column is on a different scale than the metric
    # (a 0-1 ratio scored against a target of 120, say), not that performance is terrible.
    if mean < 5:
        verdict = (
            "suspicious: samples score near 0, which usually means the wrong scale or the "
            "wrong metric — compare the value range against the target"
        )
    elif all(s == 100 for s in scores) and definition.direction == "lower_better":
        verdict = "every sample scores 100 — plausible, but check the unit is not too small"
    else:
        verdict = "plausible"

    return {
        "metric": metric,
        "column": column,
        "target": definition.target,
        "better_when": "higher" if definition.direction == "higher_better" else "lower",
        "unit": definition.unit,
        "sample_scores": scored,
        "mean_score": mean,
        "verdict": verdict,
    }


@mapping_agent.output_validator
def _validate_proposal(
    ctx: RunContext[MappingDeps], proposal: AgentMappingProposal
) -> AgentMappingProposal:
    if proposal.profile not in PROFILES:
        raise ModelRetry(
            f"Profile {proposal.profile!r} does not exist. Choose one of: "
            f"{', '.join(sorted(PROFILES))}."
        )

    allowed_metrics = get_profile(proposal.profile).metric_names()
    allowed_columns = set(ctx.deps.candidate_columns)

    seen_metrics: set[str] = set()
    seen_columns: set[str] = set()
    for suggestion in proposal.mappings:
        if suggestion.metric not in allowed_metrics:
            raise ModelRetry(
                f"Metric {suggestion.metric!r} is not part of profile {proposal.profile!r}. "
                f"Valid metrics: {', '.join(sorted(allowed_metrics))}."
            )
        if suggestion.source_column not in allowed_columns:
            raise ModelRetry(
                f"Column {suggestion.source_column!r} is not in the file. "
                f"Columns: {', '.join(sorted(allowed_columns))}."
            )
        if suggestion.metric in seen_metrics:
            raise ModelRetry(f"Metric {suggestion.metric!r} is mapped more than once.")
        if suggestion.source_column in seen_columns:
            raise ModelRetry(f"Column {suggestion.source_column!r} is mapped more than once.")
        seen_metrics.add(suggestion.metric)
        seen_columns.add(suggestion.source_column)

    for label, column in (
        ("identifier_column", proposal.identifier_column),
        ("name_column", proposal.name_column),
        ("period_column", proposal.period_column),
    ):
        if column is not None and column not in allowed_columns:
            raise ModelRetry(f"{label} {column!r} is not a column in the file.")

    return proposal


def _build_model() -> Model | None:
    """Return a pydantic-ai model, or None when no OpenAI key is configured."""
    client = get_openai_client()
    if client is None:
        return None
    settings = get_settings()
    return OpenAIChatModel(
        settings.openai_model,
        provider=OpenAIProvider(openai_client=client),
    )


async def propose_mapping(
    previews: list[ColumnPreview],
    candidate_columns: list[str],
    profile_hint: str | None = None,
) -> AgentMappingProposal | None:
    """Ask the agent to map ``candidate_columns`` onto canonical metrics.

    Returns None when AI mapping is unavailable (no API key, disabled in settings, or nothing
    left to classify) so callers can fall back to deterministic alias matching.
    """
    settings = get_settings()
    if not settings.ai_mapping_enabled or not candidate_columns:
        return None

    model = _build_model()
    if model is None:
        return None

    deps = MappingDeps(
        previews={p.column: p for p in previews},
        candidate_columns=candidate_columns,
        profile_hint=profile_hint,
    )
    try:
        result = await mapping_agent.run(
            "Classify the columns described in your instructions.",
            model=model,
            deps=deps,
        )
    except UnexpectedModelBehavior as exc:
        # Retries exhausted: the model kept proposing metrics or columns that do not exist.
        raise AIMappingError(
            "The mapping agent could not produce a valid column mapping.",
            {"reason": str(exc), "columns": candidate_columns},
        ) from exc
    except ModelHTTPError as exc:
        raise AIMappingError(
            "The mapping agent could not reach the model.", {"reason": str(exc)}
        ) from exc

    return result.output
