from functools import lru_cache

from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior, UserError
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.core.config import get_settings
from app.core.errors import AIError, AIUnavailableError

INSTRUCTIONS = """
You are a data analysis agent for an employee performance tracker.

You decide what is worth calculating from the data you are given. You never do arithmetic
yourself — call a tool for every number you report. If no tool can produce a number you
need, say so instead of estimating it.

Always explain what you chose to calculate and why.
"""


agent: Agent[None, str] = Agent(instructions=INSTRUCTIONS)


@agent.tool_plain
def add(a: float, b: float) -> float:
    """Add two numbers and return the total."""
    return a + b


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


# TODO: inspects the data and decides what is worth calculating (AGENTS.md §7). Signature
# depends on the data shape decided in AGENTS.md §5 — don't invent one ahead of that.
async def analyze() -> None:
    raise NotImplementedError


# TODO: takes analyze()'s output and explains what was chosen and why, alongside the
# results (AGENTS.md §7). Signature depends on analyze()'s return shape.
async def report() -> None:
    raise NotImplementedError
