from typing import Literal

from pydantic import BaseModel


class UploadReceipt(BaseModel):
    file_name: str
    file_type: Literal["csv", "xlsx"]
    byte_size: int
    message: str
