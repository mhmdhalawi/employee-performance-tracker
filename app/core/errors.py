from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class for expected, reportable failures."""

    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AIUnavailableError(AppError):
    """No API key is configured, so the agent cannot run."""

    status_code = 503
    code = "ai_unavailable"


class AIError(AppError):
    """The model call failed. Never raised for a missing API key."""

    status_code = 502
    code = "ai_error"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )
