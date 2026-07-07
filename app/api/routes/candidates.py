from fastapi import APIRouter, Depends, HTTPException, status

from app.agents import AIServiceAgent
from app.core.security import require_api_key
from app.schemas.candidates import CandidateScoreBatchRequest, CandidateScoreResponse

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.post("/score-batch", response_model=CandidateScoreResponse)
async def score_candidates(payload: CandidateScoreBatchRequest) -> CandidateScoreResponse:
    try:
        result = AIServiceAgent().run("candidate_scorer", payload.model_dump(by_alias=True))
        return CandidateScoreResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/score", response_model=CandidateScoreResponse)
async def score_candidate(payload: CandidateScoreBatchRequest) -> CandidateScoreResponse:
    return await score_candidates(payload)
