from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ErrorDetail


class CandidateScoreBatchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    job: dict[str, Any] = Field(default_factory=dict)
    applications: list[dict[str, Any]] = Field(default_factory=list)
    resumes: list[dict[str, Any]] = Field(default_factory=list)


class CandidateScoreResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    success: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    rankings: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    review_required: bool = Field(default=False, alias="reviewRequired")
    error: ErrorDetail | None = None
