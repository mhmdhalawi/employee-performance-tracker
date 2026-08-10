from fastapi import APIRouter

from app.core.errors import EmployeeNotFoundError
from app.core.store import BatchStore, get_store
from app.schemas.kpi import BatchResult
from app.schemas.report import ReportRequest, ReportResponse
from app.schemas.upload import BatchSummary
from app.services.ai_report import generate_report

router = APIRouter(tags=["reports"])


@router.get("/batches", response_model=list[BatchSummary])
async def list_batches() -> list[BatchSummary]:
    """Ingested batches, newest first."""
    store: BatchStore = get_store()
    return [
        BatchSummary(
            batch_id=b.batch_id,
            filename=b.filename,
            profile=b.profile,
            created_at=b.created_at.isoformat(),
            row_count=b.row_count,
            scored_count=b.scored_count,
            issue_count=len(b.issues),
        )
        for b in store.list()
    ]


@router.get("/batches/{batch_id}", response_model=BatchResult)
async def get_batch(batch_id: str) -> BatchResult:
    """Full KPI results for one batch."""
    store: BatchStore = get_store()
    return store.get(batch_id)


@router.post("/reports", response_model=ReportResponse)
async def create_report(request: ReportRequest) -> ReportResponse:
    """Generate an AI narrative explaining one employee's calculated KPIs.

    The scores are read from the stored batch; the AI only writes prose about
    them.
    """
    store: BatchStore = get_store()
    batch = store.get(request.batch_id)

    kpi = next(
        (e for e in batch.employees if e.employee_id == request.employee_id), None
    )
    if kpi is None:
        raise EmployeeNotFoundError(
            f"Employee {request.employee_id!r} is not in batch {request.batch_id!r}.",
            {"employee_id": request.employee_id, "batch_id": request.batch_id},
        )

    return await generate_report(kpi, request)
