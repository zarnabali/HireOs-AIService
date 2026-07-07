from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ErrorDetail


class InterviewGenerateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    candidate_id: str | None = Field(default=None, alias="candidateId")
    resume_id: str | None = Field(default=None, alias="resumeId")
    job_id: str | None = Field(default=None, alias="jobId")
    structured_resume: dict[str, Any] = Field(default_factory=dict, alias="structuredResume")
    job: dict[str, Any] = Field(default_factory=dict)
    focus_areas: list[str] = Field(default_factory=list, alias="focusAreas")


class MockInterviewEvaluateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    interview_session_id: str = Field(alias="interviewSessionId")
    question_id: str | None = Field(default=None, alias="questionId")
    question: str
    answer: str


class InterviewResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    success: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    review_required: bool = Field(default=False, alias="reviewRequired")
    error: ErrorDetail | None = None
