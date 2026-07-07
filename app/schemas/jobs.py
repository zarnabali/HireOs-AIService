from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ErrorDetail


class JobMatchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    candidate_id: str | None = Field(default=None, alias="candidateId")
    resume_id: str | None = Field(default=None, alias="resumeId")
    structured_resume: dict[str, Any] = Field(default_factory=dict, alias="structuredResume")
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = 20


class JobMatchResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    success: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    matches: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    review_required: bool = Field(default=False, alias="reviewRequired")
    error: ErrorDetail | None = None
