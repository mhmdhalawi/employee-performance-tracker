from datetime import date

from fastapi import APIRouter, Header, UploadFile, status

from app.core.config import get_settings
from app.schemas.tables import AnalyzeTablesRequest
from app.schemas.uploads import (
    AIInsightRequest,
    AIInsightResponse,
    AnalyzeUploadResponse,
    DashboardResponse,
    SubmissionReceipt,
)
from app.services.agent import (
    analyze_upload,
    generate_employee_insight,
)
from app.services.submissions import analyze_and_store_tables, get_aggregated_dashboard

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


@router.post(
    "/analyze-tables",
    response_model=SubmissionReceipt,
    status_code=status.HTTP_201_CREATED,
)
async def analyze_table_data(
    request: AnalyzeTablesRequest,
    idempotency_key: str | None = Header(default=None, min_length=1, max_length=200),
) -> SubmissionReceipt:
    return await analyze_and_store_tables(
        request,
        idempotency_key=idempotency_key,
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def latest_dashboard(
    employee_id: str | None = None,
    team: str | None = None,
    period_weeks: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> DashboardResponse:
    return await get_aggregated_dashboard(
        employee_id=employee_id,
        team=team,
        period_weeks=period_weeks,
        start_date=start_date,
        end_date=end_date,
    )
