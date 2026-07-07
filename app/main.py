from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.candidates import router as candidates_router
from app.api.routes.chats import router as chats_router
from app.api.routes.interviews import router as interviews_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.resumes import router as resumes_router
from app.api.routes.tasks import router as tasks_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="HireOS AI-Service",
        version="0.1.0",
        description="FastAPI service for HireOS AI features and agent tools.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(resumes_router, prefix="/ai/resumes", tags=["resumes"])
    app.include_router(jobs_router, prefix="/ai/jobs", tags=["jobs"])
    app.include_router(candidates_router, prefix="/ai/candidates", tags=["candidates"])
    app.include_router(interviews_router, prefix="/ai/interviews", tags=["interviews"])
    app.include_router(chats_router, prefix="/ai", tags=["chats"])
    app.include_router(tasks_router, prefix="/ai/tasks", tags=["tasks"])

    return app


app = create_app()
