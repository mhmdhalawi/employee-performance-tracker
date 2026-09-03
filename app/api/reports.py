from fastapi import APIRouter, Response

from app.schemas.reports import EmployeeReportPreviewResponse, EmployeeReportRequest
from app.services.reports import build_employee_report_preview

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post(
    "/employee/preview",
    response_model=EmployeeReportPreviewResponse,
)
async def preview_employee_report(
    request: EmployeeReportRequest,
    response: Response,
) -> EmployeeReportPreviewResponse:
    response.headers["Cache-Control"] = "no-store"
    return await build_employee_report_preview(request)
