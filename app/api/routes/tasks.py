from fastapi import APIRouter, Depends

from app.core.security import require_api_key
from app.schemas.tasks import TaskStatusResponse

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task(task_id: str) -> TaskStatusResponse:
    try:
        from celery.result import AsyncResult

        from app.queues.celery_app import celery_app

        result = AsyncResult(task_id, app=celery_app)
        payload = result.result if result.ready() and result.successful() else None
        error = str(result.result) if result.ready() and result.failed() else None
        return TaskStatusResponse(
            taskId=task_id,
            status=result.status,
            ready=result.ready(),
            successful=result.successful(),
            result=payload,
            error=error,
        )
    except Exception as exc:
        return TaskStatusResponse(
            taskId=task_id,
            status="UNKNOWN",
            ready=False,
            successful=False,
            error=str(exc),
        )
