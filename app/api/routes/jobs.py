from fastapi import APIRouter, Depends, HTTPException, status

from app.agents import AIServiceAgent
from app.core.security import require_api_key
from app.schemas.jobs import JobMatchRequest, JobMatchResponse

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.post("/match", response_model=JobMatchResponse)
async def match_jobs(payload: JobMatchRequest) -> JobMatchResponse:
    try:
        result = AIServiceAgent().run("job_matcher", payload.model_dump(by_alias=True))
        return JobMatchResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
