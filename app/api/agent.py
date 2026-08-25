from fastapi import APIRouter, UploadFile

from app.core.config import get_settings
from app.schemas.uploads import AnalyzeUploadResponse
from app.services.agent import analyze_upload

router = APIRouter(tags=["agent"])


@router.post("/analyze", response_model=AnalyzeUploadResponse)
async def analyze_agent(file: UploadFile) -> AnalyzeUploadResponse:
    settings = get_settings()
    contents = await file.read(settings.upload_max_bytes + 1)
    return await analyze_upload(
        file.filename,
        contents,
        settings.upload_max_bytes,
    )
