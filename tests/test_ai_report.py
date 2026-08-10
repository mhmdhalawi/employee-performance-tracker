import json

from app.schemas.common import NormalizedRecord
from app.schemas.report import ReportRequest
from app.services.ai_report import (
    SYSTEM_PROMPT,
    build_fallback_narrative,
    build_prompt,
)
from app.services.kpi_engine import calculate_employee_kpis
from app.services.profiles import get_profile


def make_kpi():
    record = NormalizedRecord(
        employee_id="E2",
        employee_name="Bob",
        profile="support",
        period="2026-07",
        metrics={
            "tickets_resolved": 60,
            "avg_response_time_minutes": 30,
            "attendance_rate": 0.9,
        },
        source_row=3,
    )
    return calculate_employee_kpis(record, get_profile("support"))


def test_system_prompt_forbids_score_generation():
    lowered = SYSTEM_PROMPT.lower()
    assert "never state, recompute, adjust or estimate a score" in lowered
    assert "do not guess" in lowered


def test_prompt_contains_computed_scores_not_raw_rows():
    kpi = make_kpi()
    prompt = build_prompt(kpi, ReportRequest(batch_id="b1", employee_id="E2"))

    payload = json.loads(prompt[prompt.index("{") :])
    assert payload["overall_score"] == kpi.overall_score
    assert payload["families"]["productivity"]["score"] is not None
    # Raw source rows must never reach the model.
    assert "raw" not in payload


def test_prompt_marks_missing_metrics_as_unavailable():
    kpi = make_kpi()
    prompt = build_prompt(kpi, ReportRequest(batch_id="b1", employee_id="E2"))
    payload = json.loads(prompt[prompt.index("{") :])

    quality = payload["families"]["quality"]
    assert quality["score"] is None
    assert all(m["available"] is False for m in quality["metrics"])


def test_fallback_narrative_has_expected_sections():
    narrative = build_fallback_narrative(make_kpi())

    for heading in ("## Summary", "## What drove the scores", "## Watch points"):
        assert heading in narrative
    assert "Bob" in narrative


def test_fallback_narrative_is_deterministic():
    kpi = make_kpi()
    assert build_fallback_narrative(kpi) == build_fallback_narrative(kpi)
