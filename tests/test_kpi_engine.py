import pytest

from app.schemas.common import NormalizedRecord
from app.services.kpi_engine import (
    calculate_employee_kpis,
    score_family,
)
from app.services.profiles import get_profile
from app.utils.numbers import normalize_metric


def make_record(**metrics: float) -> NormalizedRecord:
    return NormalizedRecord(
        employee_id="E1",
        employee_name="Test Person",
        profile="support",
        period="2026-07",
        metrics=metrics,
        source_row=2,
    )


class TestNormalizeMetric:
    def test_higher_better_at_target_is_100(self):
        assert normalize_metric(120, 120, "higher_better") == 100.0

    def test_higher_better_is_capped_at_target(self):
        assert normalize_metric(500, 120, "higher_better") == 100.0

    def test_higher_better_scales_linearly_below_target(self):
        assert normalize_metric(60, 120, "higher_better") == 50.0

    def test_lower_better_at_target_is_100(self):
        assert normalize_metric(15, 15, "lower_better") == 100.0

    def test_lower_better_below_target_is_100(self):
        assert normalize_metric(5, 15, "lower_better") == 100.0

    def test_lower_better_at_double_target_is_50(self):
        assert normalize_metric(30, 15, "lower_better") == 50.0

    def test_lower_better_treats_zero_as_perfect(self):
        assert normalize_metric(0, 2, "lower_better") == 100.0

    def test_non_positive_target_is_rejected(self):
        with pytest.raises(ValueError):
            normalize_metric(1, 0, "higher_better")


class TestScoreFamily:
    def test_perfect_metrics_score_100(self):
        profile = get_profile("support")
        record = make_record(tickets_resolved=120, avg_response_time_minutes=15)

        result = score_family("productivity", record, profile)

        assert result.score == 100.0
        assert result.missing_metrics == []

    def test_weights_are_applied(self):
        # tickets_resolved weight .6 at 50/100, response time weight .4 at 100/100
        profile = get_profile("support")
        record = make_record(tickets_resolved=60, avg_response_time_minutes=15)

        result = score_family("productivity", record, profile)

        assert result.score == pytest.approx(70.0)

    def test_missing_metric_renormalizes_remaining_weights(self):
        profile = get_profile("support")
        record = make_record(tickets_resolved=60)  # response time absent

        result = score_family("productivity", record, profile)

        # The only available metric carries the full weight.
        assert result.score == pytest.approx(50.0)
        assert result.missing_metrics == ["avg_response_time_minutes"]
        assert result.reason is not None

    def test_family_with_no_data_scores_none_not_zero(self):
        profile = get_profile("support")
        record = make_record(tickets_resolved=120)

        result = score_family("compliance", record, profile)

        assert result.score is None
        assert result.reason
        assert all(not c.available for c in result.components)

    def test_components_are_traceable_to_source_data(self):
        profile = get_profile("support")
        record = make_record(tickets_resolved=90, avg_response_time_minutes=20)

        result = score_family("productivity", record, profile)
        component = next(c for c in result.components if c.metric == "tickets_resolved")

        assert component.raw_value == 90
        assert component.target == 120
        assert component.direction == "higher_better"
        assert component.normalized_score == 75.0
        assert component.effective_weight == pytest.approx(0.6)
        assert sum(c.contribution for c in result.components if c.available) == pytest.approx(
            result.score, abs=0.05
        )


class TestCalculateEmployeeKpis:
    def test_all_three_families_are_present(self):
        profile = get_profile("support")
        result = calculate_employee_kpis(make_record(tickets_resolved=120), profile)

        assert set(result.families) == {"productivity", "quality", "compliance"}

    def test_overall_ignores_families_without_data(self):
        profile = get_profile("support")
        record = make_record(tickets_resolved=120, avg_response_time_minutes=15)

        result = calculate_employee_kpis(record, profile)

        # Only productivity has data, so overall equals it rather than being
        # dragged down by two empty families.
        assert result.overall_score == 100.0

    def test_overall_is_none_when_nothing_can_be_scored(self):
        profile = get_profile("support")
        result = calculate_employee_kpis(make_record(), profile)

        assert result.overall_score is None

    def test_scoring_is_deterministic(self):
        profile = get_profile("developer")
        record = NormalizedRecord(
            employee_id="D1",
            profile="developer",
            metrics={"tasks_completed": 18, "cycle_time_days": 4, "bugs_reported": 3},
            source_row=2,
        )

        first = calculate_employee_kpis(record, profile)
        second = calculate_employee_kpis(record, profile)

        assert first.model_dump() == second.model_dump()
