from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class for expected, reportable failures."""

    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AIUnavailableError(AppError):
    """No API key is configured, so the agent cannot run."""

    status_code = 503
    code = "ai_unavailable"


class AIError(AppError):
    """The model call failed. Never raised for a missing API key."""

    status_code = 502
    code = "ai_error"


class UnsupportedFileTypeError(AppError):
    """The uploaded file type is not supported."""

    status_code = 415
    code = "unsupported_file_type"

    def __init__(self, file_name: str) -> None:
        super().__init__(
            f"Unsupported file type for '{file_name}'. Upload a CSV or Excel file."
        )


class FileTooLargeError(AppError):
    """The uploaded file exceeds the configured size limit."""

    status_code = 413
    code = "file_too_large"

    def __init__(self, maximum_bytes: int) -> None:
        super().__init__(f"Upload exceeds the {maximum_bytes}-byte size limit.")


class InvalidAnalysisFilterError(AppError):
    """The requested employee, team, or reporting period is invalid."""

    code = "invalid_analysis_filter"


class DashboardNotFoundError(AppError):
    """No completed persisted analysis is available for the dashboard."""

    status_code = 404
    code = "dashboard_not_found"


class InsightContextExpiredError(AppError):
    """The temporary analysis context is missing or has expired."""

    status_code = 410
    code = "insight_context_expired"


class InsightUnavailableError(AppError):
    """An employee has no supported findings for AI guidance."""

    code = "insight_unavailable"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )
