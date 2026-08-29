from datetime import date

from fastapi import APIRouter, UploadFile

from app.core.config import get_settings
from app.schemas.uploads import (
    AIInsightRequest,
    AIInsightResponse,
    AnalyzeUploadResponse,
)
from app.services.agent import analyze_upload, generate_employee_insight

router = APIRouter(tags=["agent"])


@router.post("/insights", response_model=AIInsightResponse)
async def generate_insight(request: AIInsightRequest) -> AIInsightResponse:
    return await generate_employee_insight(request.analysis_id, request.employee_id)


@router.post("/analyze", response_model=AnalyzeUploadResponse)
async def analyze_agent(
    file: UploadFile,
    employee_id: str | None = None,
    team: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AnalyzeUploadResponse:
    settings = get_settings()
    contents = await file.read(settings.upload_max_bytes + 1)
    return await analyze_upload(
        file.filename,
        contents,
        settings.upload_max_bytes,
        employee_id=employee_id,
        team=team,
        start_date=start_date,
        end_date=end_date,
    )
