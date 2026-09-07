from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agent, health, reports
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.database import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    """Initialize application infrastructure before accepting requests."""
    initialize_database()
    yield


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Ingests performance data and lets an AI agent decide what to calculate.",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(agent.router, prefix=settings.api_prefix)
app.include_router(reports.router, prefix=settings.api_prefix)
