from pathlib import PurePath
from typing import Literal

from app.core.errors import FileTooLargeError, UnsupportedFileTypeError
from app.schemas.agent import UploadReceipt

FileType = Literal["csv", "xlsx"]

_FILE_TYPES: dict[str, FileType] = {
    ".csv": "csv",
    ".xlsx": "xlsx",
}


def accept_upload(
    file_name: str | None,
    contents: bytes,
    maximum_bytes: int,
) -> UploadReceipt:
    """Validate an upload's extension and size before any file parsing occurs."""
    safe_file_name = file_name or "upload"
    file_type = _FILE_TYPES.get(PurePath(safe_file_name).suffix.casefold())
    if file_type is None:
        raise UnsupportedFileTypeError(safe_file_name)
    if len(contents) > maximum_bytes:
        raise FileTooLargeError(maximum_bytes)

    return UploadReceipt(
        file_name=safe_file_name,
        file_type=file_type,
        byte_size=len(contents),
        message="Upload accepted. Structure inspection and field mapping have not run yet.",
    )
