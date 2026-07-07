from typing import Any, Literal, TypedDict

FeatureName = Literal[
    "resume_analyzer",
    "job_matcher",
    "candidate_scorer",
    "interview_generator",
    "mock_interview_evaluator",
    "hiring_assistant",
    "career_assistant",
]


class AgentState(TypedDict, total=False):
    feature: FeatureName | str
    payload: dict[str, Any]
    tool_name: str
    status: Literal["pending", "running", "success", "failed"]
    result: dict[str, Any]
    error: dict[str, Any]
