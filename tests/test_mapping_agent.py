import io

import pandas as pd
import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.core.errors import AIMappingError, SchemaValidationError
from app.schemas.mapping import AgentMappingProposal
from app.services import mapping_agent as agent_module
from app.services.file_processor import column_previews
from app.services.ingestion import ingest_file
from app.services.mapping_agent import propose_mapping

# Headers no alias table knows about, deliberately worded like a real customer export.
NOVEL_CSV = (
    "Rep Login,Cases Wrapped Up,Mean Reply Delay (min),Happiness Index,Days Present Ratio\n"
    "R1,120,15,0.92,0.99\n"
    "R2,60,30,0.70,0.90\n"
)

GOOD_PROPOSAL = {
    "profile": "support",
    "profile_reasoning": "Ticket and satisfaction columns indicate customer support.",
    "identifier_column": "Rep Login",
    "mappings": [
        {
            "source_column": "Cases Wrapped Up",
            "metric": "tickets_resolved",
            "confidence": 0.9,
            "reasoning": "Counts of closed cases.",
        },
        {
            "source_column": "Mean Reply Delay (min)",
            "metric": "avg_response_time_minutes",
            "confidence": 0.88,
            "reasoning": "Minutes to reply.",
        },
        {
            "source_column": "Happiness Index",
            "metric": "customer_satisfaction",
            "confidence": 0.8,
            "reasoning": "0-1 satisfaction ratio.",
        },
        {
            "source_column": "Days Present Ratio",
            "metric": "attendance_rate",
            "confidence": 0.75,
            "reasoning": "Ratio of days attended.",
        },
    ],
    "unmapped_columns": [],
    "notes": "All columns classified.",
}


def scripted_model(*payloads: dict, tool_calls: list[tuple[str, dict]] | None = None):
    """A FunctionModel that optionally exercises tools, then returns each payload in turn."""
    state = {"step": 0}
    pending_tools = list(tool_calls or [])

    def respond(messages: list, info: AgentInfo) -> ModelResponse:
        if pending_tools:
            name, args = pending_tools.pop(0)
            return ModelResponse(parts=[ToolCallPart(name, args)])

        output_tool = info.output_tools[0].name
        index = min(state["step"], len(payloads) - 1)
        state["step"] += 1
        return ModelResponse(parts=[ToolCallPart(output_tool, payloads[index])])

    return FunctionModel(respond)


@pytest.fixture
def previews():
    frame = pd.read_csv(io.StringIO(NOVEL_CSV), dtype=str)
    return column_previews(frame)


@pytest.fixture
def use_model(monkeypatch):
    """Install a scripted model so the agent runs without touching the network."""

    def install(*payloads: dict, tool_calls: list[tuple[str, dict]] | None = None):
        model = scripted_model(*payloads, tool_calls=tool_calls)
        monkeypatch.setattr(agent_module, "_build_model", lambda: model)
        return model

    return install


class TestColumnPreviews:
    def test_preview_captures_scale_and_numeric_ratio(self, previews):
        by_column = {p.column: p for p in previews}

        happiness = by_column["Happiness Index"]
        assert happiness.numeric_ratio == 1.0
        assert happiness.numeric_max == 0.92

        login = by_column["Rep Login"]
        assert login.numeric_ratio == 0.0  # text identifiers, not a metric
        assert login.sample_values == ["R1", "R2"]


class TestAgentTools:
    @pytest.mark.anyio
    async def test_agent_can_call_the_calculation_tools(self, previews, use_model):
        """The agent reaches list_metrics and check_mapping before deciding."""
        use_model(
            GOOD_PROPOSAL,
            tool_calls=[
                ("list_metrics", {"profile": "support"}),
                # A 0-1 ratio against a count-of-120 target scores ~0 everywhere.
                ("check_mapping", {"column": "Happiness Index", "metric": "tickets_resolved"}),
            ],
        )
        proposal = await propose_mapping(previews, [p.column for p in previews])

        assert isinstance(proposal, AgentMappingProposal)
        assert proposal.profile == "support"

    @pytest.mark.anyio
    async def test_check_mapping_verdict_catches_a_wrong_scale(self, previews):
        """Called directly: the tool's own arithmetic must expose the bad mapping."""
        deps = agent_module.MappingDeps(
            previews={p.column: p for p in previews},
            candidate_columns=[p.column for p in previews],
            profile_hint=None,
        )
        ctx = type("Ctx", (), {"deps": deps})()

        wrong = await agent_module.check_mapping(ctx, "Happiness Index", "tickets_resolved")
        right = await agent_module.check_mapping(ctx, "Cases Wrapped Up", "tickets_resolved")

        assert "suspicious" in wrong["verdict"]
        assert wrong["mean_score"] < 5
        assert right["verdict"] == "plausible"

    @pytest.mark.anyio
    async def test_invalid_metric_name_is_rejected_and_retried(self, previews, use_model):
        bogus = {
            **GOOD_PROPOSAL,
            "mappings": [
                {
                    "source_column": "Cases Wrapped Up",
                    "metric": "vibes_delivered",
                    "confidence": 0.9,
                    "reasoning": "Invented metric.",
                }
            ],
        }
        use_model(bogus, GOOD_PROPOSAL)
        proposal = await propose_mapping(previews, [p.column for p in previews])

        # First attempt was rejected by the output validator; the retry stuck.
        assert [m.metric for m in proposal.mappings] == [
            "tickets_resolved",
            "avg_response_time_minutes",
            "customer_satisfaction",
            "attendance_rate",
        ]

    @pytest.mark.anyio
    async def test_hallucinated_column_is_rejected(self, previews, use_model):
        bogus = {
            **GOOD_PROPOSAL,
            "mappings": [
                {
                    "source_column": "Column That Does Not Exist",
                    "metric": "tickets_resolved",
                    "confidence": 0.9,
                    "reasoning": "Made up.",
                }
            ],
        }
        use_model(bogus, GOOD_PROPOSAL)
        proposal = await propose_mapping(previews, [p.column for p in previews])

        assert all(
            m.source_column != "Column That Does Not Exist" for m in proposal.mappings
        )

    @pytest.mark.anyio
    async def test_duplicate_metric_is_rejected(self, previews, use_model):
        duplicated = {
            **GOOD_PROPOSAL,
            "mappings": [
                GOOD_PROPOSAL["mappings"][0],
                {**GOOD_PROPOSAL["mappings"][1], "metric": "tickets_resolved"},
            ],
        }
        use_model(duplicated, GOOD_PROPOSAL)
        proposal = await propose_mapping(previews, [p.column for p in previews])

        metrics = [m.metric for m in proposal.mappings]
        assert len(metrics) == len(set(metrics))


class TestHybridIngestion:
    @pytest.mark.anyio
    async def test_ai_mapping_makes_an_unknown_file_scorable(self, monkeypatch):
        monkeypatch.setattr(
            agent_module, "_build_model", lambda: scripted_model(GOOD_PROPOSAL)
        )

        outcome = await ingest_file("novel.csv", NOVEL_CSV.encode(), None, "hybrid")

        assert outcome.mapping_mode_used == "hybrid"
        assert outcome.batch.scored_count == 2
        assert outcome.unmapped_columns == []

        ai_mapped = {m.field: m for m in outcome.resolved_mappings if m.source == "ai"}
        assert ai_mapped["tickets_resolved"].column == "Cases Wrapped Up"
        assert ai_mapped["employee_id"].column == "Rep Login"

        # Scores come from the engine, computed off the AI's mapping.
        top = outcome.batch.employees[0]
        assert top.families["productivity"].score == 100.0
        component = next(
            c
            for c in top.families["productivity"].components
            if c.metric == "tickets_resolved"
        )
        assert component.source_field == "Cases Wrapped Up"

    @pytest.mark.anyio
    async def test_low_confidence_mapping_is_applied_but_warned(self, monkeypatch):
        unsure = {
            **GOOD_PROPOSAL,
            "mappings": [
                {**GOOD_PROPOSAL["mappings"][0], "confidence": 0.3},
                *GOOD_PROPOSAL["mappings"][1:],
            ],
        }
        monkeypatch.setattr(agent_module, "_build_model", lambda: scripted_model(unsure))

        outcome = await ingest_file("novel.csv", NOVEL_CSV.encode(), None, "hybrid")

        assert any("Low-confidence" in w for w in outcome.warnings)
        assert any(m.field == "tickets_resolved" for m in outcome.resolved_mappings)

    @pytest.mark.anyio
    async def test_aliases_still_win_over_the_agent(self, monkeypatch):
        """A file the alias tables already understand must not be sent to the agent."""
        calls = {"n": 0}

        def _model():
            calls["n"] += 1
            return scripted_model(GOOD_PROPOSAL)

        monkeypatch.setattr(agent_module, "_build_model", _model)
        known = "Employee ID,Tickets Resolved,CSAT\nE1,120,0.92\n"

        outcome = await ingest_file("known.csv", known.encode(), None, "hybrid")

        assert calls["n"] == 0  # nothing left over, so the agent was never built
        assert all(m.source == "alias" for m in outcome.resolved_mappings)

    @pytest.mark.anyio
    async def test_hybrid_degrades_to_aliases_without_a_model(self, monkeypatch):
        monkeypatch.setattr(agent_module, "_build_model", lambda: None)
        known = "Employee ID,Tickets Resolved\nE1,120\n"

        outcome = await ingest_file("known.csv", known.encode(), None, "hybrid")

        assert outcome.mapping_mode_used == "aliases"
        assert outcome.batch.scored_count == 1

    @pytest.mark.anyio
    async def test_unknown_file_without_ai_is_rejected(self, monkeypatch):
        monkeypatch.setattr(agent_module, "_build_model", lambda: None)

        with pytest.raises(SchemaValidationError):
            await ingest_file("novel.csv", NOVEL_CSV.encode(), None, "hybrid")

    @pytest.mark.anyio
    async def test_metric_from_another_profile_is_dropped_not_scored(self, monkeypatch):
        """An explicit profile always wins over the agent's choice.

        The agent answers for 'developer' (self-consistent, so the output validator passes),
        but the caller pinned 'support'. The developer-only metric must be discarded rather
        than scored against the wrong profile's targets.
        """
        cross_profile = {
            "profile": "developer",
            "profile_reasoning": "Looks like delivery work to me.",
            "identifier_column": "Rep Login",
            "mappings": [
                {
                    # Compliance metrics exist in both profiles, so this one survives.
                    "source_column": "Days Present Ratio",
                    "metric": "attendance_rate",
                    "confidence": 0.9,
                    "reasoning": "Ratio of days attended.",
                },
                {
                    "source_column": "Happiness Index",
                    "metric": "code_review_approval_rate",  # developer-only
                    "confidence": 0.9,
                    "reasoning": "Approval ratio.",
                },
            ],
            "unmapped_columns": [],
        }
        monkeypatch.setattr(
            agent_module, "_build_model", lambda: scripted_model(cross_profile)
        )

        outcome = await ingest_file("novel.csv", NOVEL_CSV.encode(), "support", "hybrid")

        assert outcome.batch.profile == "support"
        assert all(
            m.field != "code_review_approval_rate" for m in outcome.resolved_mappings
        )
        assert any("Ignored AI mapping" in w for w in outcome.warnings)
        # The cross-profile-valid metric still made it through.
        assert any(m.field == "attendance_rate" for m in outcome.resolved_mappings)

    @pytest.mark.anyio
    async def test_agent_failure_is_a_502_not_a_crash(self, monkeypatch):
        """If the model never returns a usable mapping, fail explicitly."""
        never_valid = {
            **GOOD_PROPOSAL,
            "mappings": [
                {
                    "source_column": "Cases Wrapped Up",
                    "metric": "not_a_real_metric",
                    "confidence": 0.9,
                    "reasoning": "Persistently wrong.",
                }
            ],
        }
        monkeypatch.setattr(
            agent_module, "_build_model", lambda: scripted_model(never_valid)
        )

        with pytest.raises(AIMappingError) as exc_info:
            await ingest_file("novel.csv", NOVEL_CSV.encode(), None, "hybrid")

        assert exc_info.value.status_code == 502
