from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.agent import AskRequest, AskResponse
from app.services.agent import ask

router = APIRouter(tags=["agent"])


@router.post("/ask", response_model=AskResponse)
async def ask_agent(payload: AskRequest) -> AskResponse:
    answer, total_tokens = await ask(payload.prompt)
    return AskResponse(
        answer=answer,
        model=get_settings().openai_model,
        total_tokens=total_tokens,
    )
