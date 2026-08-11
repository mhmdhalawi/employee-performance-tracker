from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


class AskResponse(BaseModel):
    answer: str
    model: str
    total_tokens: int
