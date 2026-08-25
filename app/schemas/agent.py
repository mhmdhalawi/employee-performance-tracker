from typing import Literal

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


class AskResponse(BaseModel):
    answer: str
    model: str
    total_tokens: int


class UploadReceipt(BaseModel):
    file_name: str
    file_type: Literal["csv", "xlsx"]
    byte_size: int
    message: str
