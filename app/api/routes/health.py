from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "hireos-ai-service",
        "environment": settings.environment,
    }


@router.get("/ai/health")
async def ai_health_check() -> dict[str, str]:
    return await health_check()
