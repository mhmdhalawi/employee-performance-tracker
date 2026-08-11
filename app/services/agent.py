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


@lru_cache
def get_agent() -> Agent[None, str]:
    """Build the agent once per process. Raises AIUnavailableError without an API key."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise AIUnavailableError(
            "OPENAI_API_KEY is not set, so the agent cannot run.",
            {"hint": "Copy .env.example to .env and set OPENAI_API_KEY."},
        )

    # The key comes from Settings (.env), not from the ambient environment, so the
    # provider is constructed explicitly rather than by the "openai:<model>" shorthand.
    model = OpenAIChatModel(
        settings.openai_model,
        provider=OpenAIProvider(api_key=settings.openai_api_key),
    )
    agent: Agent[None, str] = Agent(model, instructions=INSTRUCTIONS)

    # Placeholder tool: proves the tool loop works end to end. Real calculation tools
    # replace this once we have seen an actual data file (see AGENTS.md sections 5-6).
    @agent.tool_plain
    def add(a: float, b: float) -> float:
        """Add two numbers and return the total."""
        return a + b

    return agent


async def ask(prompt: str) -> tuple[str, int]:
    """Run the agent against ``prompt``. Returns its answer and the tokens used."""
    agent = get_agent()
    try:
        result = await agent.run(prompt)
    except (UnexpectedModelBehavior, UserError) as exc:
        raise AIError(f"The model call failed: {exc}") from exc

    return result.output, result.usage.total_tokens
