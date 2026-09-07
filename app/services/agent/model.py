from functools import lru_cache

from pydantic_ai import Agent
from pydantic_ai.models.openai import (
    OpenAIResponsesModel,
    OpenAIResponsesModelSettings,
)
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from app.core.config import get_settings
from app.core.errors import AIUnavailableError
from app.schemas.uploads import AgentCalculationPlan
from app.services.agent.prompts import MAPPING_AGENT_INSTRUCTIONS

analysis_agent = Agent[None, AgentCalculationPlan](
    name="employee_performance_agent",
    instructions=MAPPING_AGENT_INSTRUCTIONS,
    deps_type=type(None),
    output_type=AgentCalculationPlan,
)

@lru_cache
def get_model() -> OpenAIResponsesModel:
    """Return the configured model or raise when no API key is available."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise AIUnavailableError("OPENAI_API_KEY is not set, so the agent cannot run.")

    return OpenAIResponsesModel(
        settings.openai_model,
        provider=OpenAIProvider(api_key=settings.openai_api_key),
    )

def _mapping_model_settings() -> OpenAIResponsesModelSettings:
    return OpenAIResponsesModelSettings(
        openai_prompt_cache_key="employee-performance-mapping-v1",
        openai_text_verbosity="low",
    )


def _mapping_usage_limits() -> UsageLimits:
    return UsageLimits(
        request_limit=3,
        total_tokens_limit=60_000,
    )

