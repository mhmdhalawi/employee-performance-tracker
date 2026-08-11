from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.agent import AskRequest, AskResponse
from app.services.agent import analyze, ask, report

router = APIRouter(tags=["agent"])


@router.post("/ask", response_model=AskResponse)
async def ask_agent(payload: AskRequest) -> AskResponse:
    answer, total_tokens = await ask(payload.prompt)
    return AskResponse(
        answer=answer,
        model=get_settings().openai_model,
        total_tokens=total_tokens,
    )


# TODO: request/response schema depends on the data shape decided in AGENTS.md §5.
@router.post("/analyze")
async def analyze_agent() -> None:
    await analyze()


# TODO: request/response schema depends on analyze()'s return shape (AGENTS.md §7).
@router.post("/report")
async def report_agent() -> None:
    await report()
