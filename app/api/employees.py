from datetime import date

from fastapi import APIRouter, Response

from app.schemas.employee_evidence import EmployeeEvidenceResponse
from app.services.employee_evidence import get_employee_evidence

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("/{employee_id}/evidence", response_model=EmployeeEvidenceResponse)
async def employee_evidence(
    employee_id: str,
    response: Response,
    kpi: str,
    page: int = 1,
    page_size: int = 5,
    start_date: date | None = None,
    end_date: date | None = None,
    period_weeks: int | None = None,
) -> EmployeeEvidenceResponse:
    response.headers["Cache-Control"] = "no-store"
    return await get_employee_evidence(
        employee_id, kpi, page, page_size, start_date, end_date, period_weeks
    )
