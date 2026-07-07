from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.candidate_scorer_service import CandidateScorerService
from app.services.chat_services import CareerAssistantService, HiringAssistantService
from app.services.interview_service import InterviewService
from app.services.job_matcher_service import JobMatcherService
from app.services.resume_analyzer_service import ResumeAnalyzerService


class AgentToolInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    payload: dict[str, Any] = Field(default_factory=dict)


class AgentToolOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    success: bool
    tool_name: str = Field(alias="toolName")
    result: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class AgentTool:
    name: str
    feature: str
    description: str
    handler: Callable[[dict[str, Any]], dict[str, Any]]

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            validated = AgentToolInput(payload=payload)
            result = self.handler(validated.payload)
            return AgentToolOutput(
                success=True,
                toolName=self.name,
                result=result,
                warnings=result.get("warnings", []) if isinstance(result, dict) else [],
            ).model_dump(by_alias=True)
        except ValidationError as exc:
            return self._failed("INVALID_TOOL_INPUT", "Agent tool input failed validation.", exc.errors())
        except ValueError as exc:
            return self._failed("TOOL_BAD_REQUEST", str(exc), [])
        except RuntimeError as exc:
            return self._failed("TOOL_RUNTIME_ERROR", str(exc), [])

    def _failed(self, code: str, message: str, details: list[Any]) -> dict[str, Any]:
        return AgentToolOutput(
            success=False,
            toolName=self.name,
            error={"code": code, "message": message, "details": details},
        ).model_dump(by_alias=True)


def _resume_analyzer(payload: dict[str, Any]) -> dict[str, Any]:
    return ResumeAnalyzerService().analyze(payload)


def _job_matcher(payload: dict[str, Any]) -> dict[str, Any]:
    return JobMatcherService().match(payload)


def _candidate_scorer(payload: dict[str, Any]) -> dict[str, Any]:
    return CandidateScorerService().score_batch(payload)


def _interview_generator(payload: dict[str, Any]) -> dict[str, Any]:
    return InterviewService().generate(payload)


def _mock_interview_evaluator(payload: dict[str, Any]) -> dict[str, Any]:
    return InterviewService().evaluate_mock_answer(payload)


def _hiring_assistant(payload: dict[str, Any]) -> dict[str, Any]:
    return HiringAssistantService().chat(payload)


def _career_assistant(payload: dict[str, Any]) -> dict[str, Any]:
    return CareerAssistantService().chat(payload)


TOOLS_BY_FEATURE: dict[str, AgentTool] = {
    "resume_analyzer": AgentTool(
        name="analyze_resume",
        feature="resume_analyzer",
        description="Analyze structured resume data for ATS score, issues, and improvements.",
        handler=_resume_analyzer,
    ),
    "job_matcher": AgentTool(
        name="match_jobs_to_candidate",
        feature="job_matcher",
        description="Rank jobs against a candidate resume and preferences with evidence.",
        handler=_job_matcher,
    ),
    "candidate_scorer": AgentTool(
        name="score_candidate_batch",
        feature="candidate_scorer",
        description="Score candidate resumes against a recruiter job description.",
        handler=_candidate_scorer,
    ),
    "interview_generator": AgentTool(
        name="generate_interview_kit",
        feature="interview_generator",
        description="Generate role-specific interview questions from resume and job context.",
        handler=_interview_generator,
    ),
    "mock_interview_evaluator": AgentTool(
        name="evaluate_interview_response",
        feature="mock_interview_evaluator",
        description="Evaluate a candidate mock interview answer with scores and feedback.",
        handler=_mock_interview_evaluator,
    ),
    "hiring_assistant": AgentTool(
        name="recruiter_assistant_chat",
        feature="hiring_assistant",
        description="Plan scoped recruiter actions such as candidate search, shortlist, and comparison.",
        handler=_hiring_assistant,
    ),
    "career_assistant": AgentTool(
        name="candidate_career_chat",
        feature="career_assistant",
        description="Plan candidate career coach actions for resume, jobs, interviews, and skills.",
        handler=_career_assistant,
    ),
}
