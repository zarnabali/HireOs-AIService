from typing import Any

from pydantic import BaseModel, Field


class TaskStatusResponse(BaseModel):
    task_id: str = Field(alias="taskId")
    status: str
    ready: bool = False
    successful: bool = False
    result: Any = None
    error: str | None = None
