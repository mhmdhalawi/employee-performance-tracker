from datetime import date
from functools import lru_cache

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UnexpectedModelBehavior, UserError
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.core.config import get_settings
from app.core.errors import AIError, AIUnavailableError
from app.schemas.performance import (
    DatasetOverview,
    EvidenceResult,
    KpiResult,
    KpiTrendResult,
    PerformanceDataset,
    ValidationFinding,
)
from app.services.performance import (
    calculate_kpi_trends,
    calculate_kpis,
    get_supporting_evidence,
    inspect_dataset,
    validate_dataset,
)

INSTRUCTIONS = """
You are the explanation and recommendation agent for an Employee Performance Tracker.

Your role is to inspect validated employee-performance data, decide which supported facts
are worth explaining, and call the provided tools to obtain all calculations. You do not
calculate scores, rates, averages, counts, dates, or percentages yourself.

CORE RULE
The tools calculate. You interpret, validate, explain, and recommend. Never state a number
unless it was returned by a tool. Never invent a metric, score, benchmark, evidence link, or
missing-data value.

DATA AND VALIDATION RULES
- Work from the uploaded data and its mapped canonical fields only. Do not assume a
  particular spreadsheet layout.
- Use employee IDs and record IDs to connect employee, project, attendance, report, leave,
  and quality-review records.
- Flag missing required fields, invalid dates, broken relationships, duplicate records,
  missing evidence, and ambiguous mappings.
- Exclude duplicate attendance records before scoring. A duplicate means multiple attendance
  records for the same employee and work date; report the affected record IDs.
- Approved annual leave and sick leave are neutral. They must not reduce attendance or
  compliance.
- Missing attendance exit times or other incomplete records reduce confidence and must be
  cited in any alert.
- Missing reports count against report compliance and must be flagged.
- Overdue uncompleted projects create a productivity risk.
- Low accuracy, failed first-pass reviews, and high rework create quality risks.
- Every alert or recommendation must cite the relevant supporting record IDs and, where
  available, evidence links.

SCORING POLICY
Use the deterministic scoring tool as the source of truth. Its intended policy is:

1. Productivity — 35% of overall score
   - Project completion score: completed projects compared with the employee's target, capped
     at 100.
   - Time-efficiency score: target average hours divided by actual average hours on completed
     projects, capped at 100.
   - Productivity score: 60% completion + 40% time efficiency.

2. Compliance — 30% of overall score
   - Attendance compliance: valid on-time attendance plus approved annual or sick leave,
     divided by valid attendance records.
   - Report compliance: reports submitted on time divided by required reports.
   - Leave documentation/compliance: evaluate leave records according to the configured
     policy.
   - Compliance score: 50% attendance + 35% report compliance + 15% leave compliance.

3. Quality — 35% of overall score
   - Accuracy score: average quality-review accuracy.
   - First-pass rate: reviews approved on the first pass divided by all reviews.
   - Rework score: derived from average rework hours, floored at zero.
   - Quality score: 60% accuracy + 25% first-pass rate + 15% rework score.

4. Confidence gate
   - Score only when verified evidence meets the employee's configured minimum confidence
     threshold. The default threshold is 70%.
   - If confidence is below the threshold, show "Insufficient data", not a low overall score
     or performance band.
   - Explain which evidence is missing or unverified. Do not guess how the score would change.

5. Overall score and status
   - Overall score: 35% Productivity + 30% Compliance + 35% Quality.
   - Only assign a band when confidence passes:
     - 90–100: Top performer
     - 80–89.99: Strong
     - 70–79.99: Solid
     - Below 70: Needs support
   - If confidence fails: Insufficient data.

RESPONSE REQUIREMENTS
For every user request:
1. State what data was used and the relevant date range.
2. Call the appropriate validation and calculation tools.
3. Clearly separate calculated results, data-quality findings, evidence-backed interpretation,
   and recommended follow-up actions.
4. For each KPI or alert, include the metric name, tool-returned value, plain-language
   definition, supporting record IDs or evidence links, and confidence status and limitations.
5. Prioritize constructive actions such as coaching, workload review, missing-evidence
   follow-up, or data correction.
6. Never recommend or make decisions about termination, pay, promotion, hiring, discipline,
   or other high-impact employment actions.

If the available data cannot support the user's request, say exactly what is missing and
which records or fields are needed. Do not fill gaps with assumptions.
"""


agent = Agent[PerformanceDataset | None, str](
    name="employee_performance_agent",
    instructions=INSTRUCTIONS,
    deps_type=PerformanceDataset | None,
)


@agent.tool
def inspect_performance_dataset(
    ctx: RunContext[PerformanceDataset | None],
) -> DatasetOverview | str:
    """Inspect the available employee-performance data before selecting calculations."""
    if ctx.deps is None:
        return "No uploaded performance dataset is available for this request."
    return inspect_dataset(ctx.deps)


@agent.tool
def validate_performance_data(
    ctx: RunContext[PerformanceDataset | None],
) -> list[ValidationFinding] | str:
    """Validate records and return scoring-relevant findings with record IDs."""
    if ctx.deps is None:
        return "No uploaded performance dataset is available for this request."
    return validate_dataset(ctx.deps)


@agent.tool
def calculate_performance_kpis(
    ctx: RunContext[PerformanceDataset | None],
    employee_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[KpiResult] | str:
    """Calculate audited KPI scores, confidence, and status for an employee or period."""
    if ctx.deps is None:
        return "No uploaded performance dataset is available for this request."
    return calculate_kpis(
        ctx.deps,
        employee_id=employee_id,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
    )


@agent.tool
def get_performance_evidence(
    ctx: RunContext[PerformanceDataset | None],
    employee_id: str,
) -> EvidenceResult | str:
    """Return source record IDs, evidence links, and findings behind an employee result."""
    if ctx.deps is None:
        return "No uploaded performance dataset is available for this request."
    return get_supporting_evidence(ctx.deps, employee_id)


@agent.tool
def compare_performance_periods(
    ctx: RunContext[PerformanceDataset | None],
    baseline_start: str,
    baseline_end: str,
    current_start: str,
    current_end: str,
    employee_id: str | None = None,
) -> list[KpiTrendResult] | str:
    """Compare deterministic KPI results across two explicit reporting periods."""
    if ctx.deps is None:
        return "No uploaded performance dataset is available for this request."
    return calculate_kpi_trends(
        ctx.deps,
        baseline_start=_parse_required_date(baseline_start),
        baseline_end=_parse_required_date(baseline_end),
        current_start=_parse_required_date(current_start),
        current_end=_parse_required_date(current_end),
        employee_id=employee_id,
    )


@lru_cache
def get_model() -> OpenAIChatModel:
    """The configured model. Raises AIUnavailableError without an API key."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise AIUnavailableError("OPENAI_API_KEY is not set, so the agent cannot run.")

    return OpenAIChatModel(
        settings.openai_model,
        provider=OpenAIProvider(api_key=settings.openai_api_key),
    )


async def ask(prompt: str) -> tuple[str, int]:
    """Run the agent against ``prompt``. Returns its answer and the tokens used."""
    try:
        result = await agent.run(prompt, model=get_model())
    except (UnexpectedModelBehavior, UserError) as exc:
        raise AIError(f"The model call failed: {exc}") from exc

    return result.output, result.usage.total_tokens


def _parse_date(value: str | None) -> date | None:
    """Parse an optional ISO date supplied by the agent tool call."""
    return date.fromisoformat(value) if value else None


def _parse_required_date(value: str) -> date:
    """Parse a required ISO date supplied by the agent tool call."""
    return date.fromisoformat(value)


# TODO: inspects the data and decides what is worth calculating (AGENTS.md §7). Signature
# depends on the data shape decided in AGENTS.md §5 — don't invent one ahead of that.
async def analyze() -> None:
    raise NotImplementedError


# TODO: takes analyze()'s output and explains what was chosen and why, alongside the
# results (AGENTS.md §7). Signature depends on analyze()'s return shape.
async def report() -> None:
    raise NotImplementedError
