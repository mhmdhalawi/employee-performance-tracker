import json

from app.core.config import get_settings
from app.core.errors import AIReportError
from app.core.openai_client import get_openai_client
from app.schemas.kpi import EmployeeKpiResult, KpiFamilyScore
from app.schemas.report import ReportRequest, ReportResponse

SYSTEM_PROMPT = """\
You are a performance analyst writing about an employee's KPI results.

The scores you are given were calculated by a deterministic backend engine. Your job is to
explain them, not to judge or recompute them.

Rules you must follow:
- Never state, recompute, adjust or estimate a score. Quote the given numbers exactly.
- Never invent a metric that is not in the data you were given.
- If a metric or family is marked unavailable, say the data is missing. Do not guess its value
  and do not treat missing data as poor performance.
- Every claim must be traceable to a metric in the payload: reference the metric, its value and
  its target.
- Be specific and neutral. No motivational filler, no speculation about the person's intent,
  attitude or personal circumstances.

Structure your answer with these markdown sections:
## Summary
## What drove the scores
## Watch points
## Suggested next steps

Keep it under 400 words.\
"""


def _family_payload(score: KpiFamilyScore) -> dict:
    """Compact, model-friendly view of one family. Only computed values."""
    return {
        "score": score.score,
        "score_missing_reason": score.reason if score.score is None else None,
        "note": score.reason if score.score is not None else None,
        "metrics": [
            {
                "metric": c.label,
                "available": c.available,
                "value": c.raw_value,
                "unit": c.unit,
                "target": c.target,
                "better_when": "higher" if c.direction == "higher_better" else "lower",
                "metric_score": c.normalized_score,
                "weight_in_family": c.effective_weight,
                "source_column": c.source_field,
                "note": c.note,
            }
            for c in score.components
        ],
        "missing_metrics": score.missing_metrics,
    }


def build_prompt(kpi: EmployeeKpiResult, request: ReportRequest) -> str:
    """Serialize the computed result for the model.

    Only calculated values are sent — never the raw uploaded file — so the model
    has nothing to recompute from.
    """
    payload = {
        "employee_id": kpi.employee_id,
        "employee_name": kpi.employee_name,
        "role_profile": kpi.profile,
        "period": kpi.period,
        "overall_score": kpi.overall_score,
        "scale": "All scores are 0-100, where 100 means the target was met or exceeded.",
        "families": {
            family: _family_payload(score) for family, score in kpi.families.items()
        },
    }
    return (
        f"Audience: {request.audience}. Write in language code: {request.language}.\n\n"
        "Calculated KPI data (authoritative — do not alter these numbers):\n"
        f"{json.dumps(payload, indent=2, ensure_ascii=False)}"
    )


def build_fallback_narrative(kpi: EmployeeKpiResult) -> str:
    """Deterministic template used when no API key is configured.

    Mirrors the structure of the AI output so the dashboard renders both the same
    way, and keeps local development fully functional without a key.
    """
    name = kpi.employee_name or kpi.employee_id
    overall = "not available" if kpi.overall_score is None else f"{kpi.overall_score}/100"
    lines = [
        "## Summary",
        f"{name} ({kpi.profile}) has an overall score of {overall}"
        + (f" for {kpi.period}." if kpi.period else "."),
        "",
        "## What drove the scores",
    ]

    for family, score in kpi.families.items():
        if score.score is None:
            lines.append(f"- **{family.title()}**: no score — {score.reason}")
            continue
        drivers = sorted(
            (c for c in score.components if c.available and c.normalized_score is not None),
            key=lambda c: c.normalized_score or 0.0,
        )
        detail = ", ".join(
            f"{c.label} {c.raw_value}{'' if not c.unit else ' ' + c.unit}"
            f" vs target {c.target} ({c.normalized_score}/100)"
            for c in drivers
        )
        lines.append(f"- **{family.title()}**: {score.score}/100 — {detail or 'no metrics'}")

    watch = [
        f"- {c.label} scored {c.normalized_score}/100 against a target of {c.target}."
        for score in kpi.families.values()
        for c in score.components
        if c.available and (c.normalized_score or 100) < 70
    ]
    missing = [m for score in kpi.families.values() for m in score.missing_metrics]

    lines += ["", "## Watch points"]
    lines += watch or ["- No metric scored below 70."]
    if missing:
        lines.append(
            f"- Missing from the source data ({len(missing)}): {', '.join(sorted(set(missing)))}."
        )

    lines += [
        "",
        "## Suggested next steps",
        "- Review the metrics listed under watch points with the employee.",
        "- Supply any missing metrics in the next upload for a complete picture.",
        "",
        "_Generated without the AI model (no OPENAI_API_KEY configured)._",
    ]
    return "\n".join(lines)


async def generate_report(kpi: EmployeeKpiResult, request: ReportRequest) -> ReportResponse:
    """Produce a narrative for an already-scored employee.

    Falls back to the deterministic template when AI is not configured. Raises
    AIReportError only when a configured OpenAI call actually fails.
    """
    settings = get_settings()
    client = get_openai_client()

    if client is None:
        return ReportResponse(
            batch_id=request.batch_id,
            employee_id=kpi.employee_id,
            generated_by="fallback",
            model=None,
            narrative=build_fallback_narrative(kpi),
            kpi=kpi,
        )

    try:
        completion = await client.chat.completions.create(
            model=settings.openai_model,
            # Low temperature: this is explanation of fixed numbers, not creative writing.
            temperature=0.2,
            max_tokens=settings.openai_max_output_tokens,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_prompt(kpi, request)},
            ],
        )
    except Exception as exc:
        raise AIReportError(
            "Failed to generate the AI report.", {"reason": str(exc)}
        ) from exc

    narrative = (completion.choices[0].message.content or "").strip()
    if not narrative:
        raise AIReportError("The AI returned an empty report.")

    return ReportResponse(
        batch_id=request.batch_id,
        employee_id=kpi.employee_id,
        generated_by="openai",
        model=settings.openai_model,
        narrative=narrative,
        kpi=kpi,
    )
