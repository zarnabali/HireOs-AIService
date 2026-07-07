from fastapi import APIRouter, Depends, HTTPException, status

from app.agents import AIServiceAgent
from app.core.security import require_api_key
from app.schemas.chats import CandidateChatRequest, ChatResponse, RecruiterChatRequest

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.post("/recruiter/chat", response_model=ChatResponse)
async def recruiter_chat(payload: RecruiterChatRequest) -> ChatResponse:
    try:
        result = AIServiceAgent().run("hiring_assistant", payload.model_dump(by_alias=True))
        return ChatResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/candidate/chat", response_model=ChatResponse)
async def candidate_chat(payload: CandidateChatRequest) -> ChatResponse:
    try:
        result = AIServiceAgent().run("career_assistant", payload.model_dump(by_alias=True))
        return ChatResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
