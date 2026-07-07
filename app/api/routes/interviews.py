from fastapi import APIRouter, Depends, HTTPException, status

from app.agents import AIServiceAgent
from app.core.security import require_api_key
from app.schemas.interviews import (
    InterviewGenerateRequest,
    InterviewResponse,
    MockInterviewEvaluateRequest,
)

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.post("/generate", response_model=InterviewResponse)
async def generate_interview(payload: InterviewGenerateRequest) -> InterviewResponse:
    try:
        result = AIServiceAgent().run("interview_generator", payload.model_dump(by_alias=True))
        return InterviewResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/mock/evaluate", response_model=InterviewResponse)
async def evaluate_mock_answer(payload: MockInterviewEvaluateRequest) -> InterviewResponse:
    try:
        result = AIServiceAgent().run("mock_interview_evaluator", payload.model_dump(by_alias=True))
        return InterviewResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
