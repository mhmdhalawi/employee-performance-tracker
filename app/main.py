import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

APP_NAME = "Performance Tracking Agent"
API_PREFIX = "/api/v1"

# Vue dev server by default.
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


class HealthResponse(BaseModel):
    status: str
    app_name: str
    ai_enabled: bool


def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_NAME,
        description="Ingests performance data and lets an AI agent decide what to calculate.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get(f"{API_PREFIX}/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            app_name=APP_NAME,
            ai_enabled=bool(os.environ.get("OPENAI_API_KEY")),
        )

    return app


app = create_app()


def run() -> None:
    """Console-script entrypoint: ``uv run tracker``."""
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
