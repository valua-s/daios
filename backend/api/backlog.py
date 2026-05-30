from __future__ import annotations

from dishka.integrations.litestar import FromDishka
from litestar import Controller, delete, get, post
from litestar.exceptions import NotFoundException

from backend.api.schemas import (
    BacklogItemDTO,
    CreateBacklogItemRequest,
    TaskDTO,
)
from backend.models.backlog import BacklogItem
from backend.models.task import Task
from backend.services.task_service import TaskService


def _item_to_dto(item: BacklogItem) -> BacklogItemDTO:
    return BacklogItemDTO(
        id=item.id,
        title=item.title,
        reason=item.reason,
        notes=item.notes,
    )


def _task_to_dto(task: Task) -> TaskDTO:
    return TaskDTO(
        id=task.id,
        title=task.title,
        status=task.status.value,
        priority=task.priority.value,
        scheduled_date=task.scheduled_date,
        scheduled_time=task.scheduled_time,
        source=task.source,
        notes=task.notes,
    )


class BacklogController(Controller):
    path = "/api/backlog"

    @get("/")
    async def get_backlog(self, task_service: FromDishka[TaskService]) -> list[BacklogItemDTO]:  # noqa: PLR6301
        items = await task_service.get_backlog()
        return [_item_to_dto(i) for i in items]

    @post("/")
    async def create_backlog_item(  # noqa: PLR6301
        self,
        data: CreateBacklogItemRequest,
        task_service: FromDishka[TaskService],
    ) -> BacklogItemDTO:
        item = await task_service.create_backlog_item(
            title=data.title,
            reason=data.reason,
            notes=data.notes,
        )
        return _item_to_dto(item)

    @post("/{item_id:int}/today")
    async def move_to_today(  # noqa: PLR6301
        self,
        item_id: int,
        task_service: FromDishka[TaskService],
    ) -> TaskDTO:
        task = await task_service.move_from_backlog_to_today(item_id)
        if task is None:
            raise NotFoundException(detail=f"Backlog item {item_id} not found")
        return _task_to_dto(task)

    @delete("/{item_id:int}")
    async def delete_item(  # noqa: PLR6301
        self,
        item_id: int,
        task_service: FromDishka[TaskService],
    ) -> None:
        ok = await task_service.delete_backlog_item(item_id)
        if not ok:
            raise NotFoundException(detail=f"Backlog item {item_id} not found")
