from fastapi import APIRouter, File, Form, UploadFile

from app.core.store import BatchStore, get_store
from app.schemas.mapping import MappingMode
from app.schemas.upload import MetricInfo, ProfileInfo, UploadResponse
from app.services.ingestion import ingest_file
from app.services.profiles import list_profiles

router = APIRouter(tags=["ingestion"])


@router.get("/profiles", response_model=list[ProfileInfo])
async def get_profiles() -> list[ProfileInfo]:
    """Role profiles and the columns each one accepts (dashboard hint)."""
    return [
        ProfileInfo(
            key=profile.key,
            label=profile.label,
            description=profile.description,
            metrics=[
                MetricInfo(
                    metric=m.name,
                    label=m.label,
                    family=m.family,
                    direction=m.direction,
                    target=m.target,
                    weight=m.weight,
                    unit=m.unit,
                    accepted_columns=m.accepted_columns(),
                )
                for m in profile.metrics
            ],
        )
        for profile in list_profiles()
    ]


@router.post("/uploads", response_model=UploadResponse, status_code=201)
async def upload_performance_file(
    file: UploadFile = File(description="CSV or Excel file of performance data."),
    profile: str | None = Form(
        default=None,
        description="Role profile key. Omit to auto-detect from the file's columns.",
    ),
    mapping_mode: MappingMode = Form(
        default="hybrid",
        description=(
            "'aliases' = declared column aliases only. 'hybrid' = aliases first, AI agent for "
            "leftover columns. 'ai' = the agent maps every column. AI modes fall back to "
            "'aliases' when no model is configured."
        ),
    ),
) -> UploadResponse:
    """Ingest a performance file and return calculated KPI results.

    Row-level problems are returned in ``issues`` with a 201 — only an unusable
    file produces an error status.
    """
    content = await file.read()
    outcome = await ingest_file(
        file.filename or "upload", content, profile, mapping_mode
    )

    store: BatchStore = get_store()
    store.save(outcome.batch)

    return UploadResponse.from_outcome(outcome)
