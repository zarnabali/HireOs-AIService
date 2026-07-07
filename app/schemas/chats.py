from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ErrorDetail


class RecruiterChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    recruiter_id: str | None = Field(default=None, alias="recruiterId")
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class CandidateChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    candidate_id: str | None = Field(default=None, alias="candidateId")
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    success: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    message: str = ""
    intent: str = "general"
    actions: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    review_required: bool = Field(default=False, alias="reviewRequired")
    error: ErrorDetail | None = None
