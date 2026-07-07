from fastapi import APIRouter, Depends, HTTPException, status

from app.agents import AIServiceAgent
from app.core.security import require_api_key
from app.schemas.resumes import ResumeExtractionRequest, ResumeExtractionResponse
from app.services.resume_extractor_service import ResumeExtractorService

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.post("/extract", response_model=ResumeExtractionResponse)
async def extract_resume(
    payload: ResumeExtractionRequest,
) -> ResumeExtractionResponse:
    try:
        return ResumeExtractorService().extract(payload)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/analyze")
async def analyze_resume(payload: dict) -> dict:
    try:
        return AIServiceAgent().run("resume_analyzer", payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
