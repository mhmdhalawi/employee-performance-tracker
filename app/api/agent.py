from fastapi import APIRouter, UploadFile

from app.core.config import get_settings
from app.schemas.agent import AskRequest, AskResponse
from app.schemas.uploads import AnalyzeUploadResponse
from app.services.agent import ask, report
from app.services.imports import import_performance_upload

router = APIRouter(tags=["agent"])


@router.post("/ask", response_model=AskResponse)
async def ask_agent(payload: AskRequest) -> AskResponse:
    answer, total_tokens = await ask(payload.prompt)
    return AskResponse(
        answer=answer,
        model=get_settings().openai_model,
        total_tokens=total_tokens,
    )


@router.post("/analyze", response_model=AnalyzeUploadResponse)
async def analyze_agent(file: UploadFile) -> AnalyzeUploadResponse:
    settings = get_settings()
    contents = await file.read(settings.upload_max_bytes + 1)
    return import_performance_upload(file.filename, contents, settings.upload_max_bytes)


# TODO: request/response schema depends on analyze()'s return shape (AGENTS.md §7).
@router.post("/report")
async def report_agent() -> None:
    await report()
