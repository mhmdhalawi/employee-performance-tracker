from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.common import ErrorDetail, ErrorResponse


class AppError(Exception):
    """Base class for expected, reportable failures."""

    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class UnsupportedFileTypeError(AppError):
    status_code = 415
    code = "unsupported_file_type"


class FileTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"


class FileParseError(AppError):
    """The file could not be read as a table at all."""

    status_code = 422
    code = "file_parse_error"


class SchemaValidationError(AppError):
    """The table was read but is unusable (e.g. no employee identifier column)."""

    status_code = 422
    code = "schema_validation_error"


class UnknownProfileError(AppError):
    status_code = 400
    code = "unknown_profile"


class BatchNotFoundError(AppError):
    status_code = 404
    code = "batch_not_found"


class EmployeeNotFoundError(AppError):
    status_code = 404
    code = "employee_not_found"


class AIReportError(AppError):
    """The OpenAI call failed. Never raised for a missing API key."""

    status_code = 502
    code = "ai_report_error"


class AIMappingError(AppError):
    """The column-mapping agent failed or could not produce a valid mapping."""

    status_code = 502
    code = "ai_mapping_error"


def _payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, details=details or {}))
    return body.model_dump()


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_payload(
                "request_validation_error",
                "Request payload is invalid.",
                {"errors": exc.errors()},
            ),
        )
