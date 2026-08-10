from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.kpi import EmployeeKpiResult


class ReportRequest(BaseModel):
    batch_id: str
    employee_id: str
    language: str = Field(default="en", description="Output language for the narrative.")
    audience: Literal["manager", "employee", "hr"] = "manager"


class ReportResponse(BaseModel):
    batch_id: str
    employee_id: str
    generated_by: Literal["openai", "fallback"] = Field(
        description="'fallback' means no API key was configured; text is a deterministic template."
    )
    model: str | None = None
    narrative: str
    kpi: EmployeeKpiResult = Field(
        description="The exact scores the narrative was written from."
    )
