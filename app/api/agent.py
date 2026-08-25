from fastapi import APIRouter, UploadFile

from app.core.config import get_settings
from app.schemas.agent import AskRequest, AskResponse
from app.schemas.uploads import AnalyzeUploadResponse
from app.services.agent import analyze_upload, ask

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
    return await analyze_upload(
        file.filename,
        contents,
        settings.upload_max_bytes,
    )
