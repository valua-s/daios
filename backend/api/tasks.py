from __future__ import annotations

from datetime import date, time

from dishka.integrations.litestar import FromDishka
from litestar import Controller, delete, get, patch, post
from litestar.exceptions import NotFoundException
from litestar.params import Parameter

from backend.api.schemas import CreateTaskRequest, TaskDTO, UpdateTaskRequest
from backend.models.task import Task
from backend.services.task_service import TaskService


def _to_dto(task: Task) -> TaskDTO:
    return TaskDTO(
        id=task.id,
        title=task.title,
        status=task.status.value,
        priority=task.priority.value,
        date=task.date,
        scheduled_time=task.scheduled_time,
        source=task.source,
        notes=task.notes,
    )


class TaskController(Controller):
    path = "/api/tasks"

    @get("/today")
    async def get_today(self, task_service: FromDishka[TaskService]) -> list[TaskDTO]:
        tasks = await task_service.get_today_tasks()
        return [_to_dto(t) for t in tasks]

    @get("/range")
    async def get_range(
        self,
        task_service: FromDishka[TaskService],
        from_date: date = Parameter(query="from"),
        to_date: date = Parameter(query="to"),
    ) -> list[TaskDTO]:
        tasks = await task_service.get_tasks_by_range(from_date, to_date)
        return [_to_dto(t) for t in tasks]

    @post("/")
    async def create_task(
        self,
        data: CreateTaskRequest,
        task_service: FromDishka[TaskService],
    ) -> TaskDTO:
        task = await task_service.create_task(
            title=data.title,
            priority=data.priority,
            source=data.source,
            target_date=data.date,
            scheduled_time=data.scheduled_time,
            notes=data.notes,
        )
        return _to_dto(task)

    @patch("/{task_id:int}")
    async def update_task(
        self,
        task_id: int,
        data: UpdateTaskRequest,
        task_service: FromDishka[TaskService],
    ) -> TaskDTO:
        fields: dict = {}
        if data.title is not None:
            fields["title"] = data.title
        if data.date is not None:
            fields["date"] = data.date
        if data.clear_time:
            fields["scheduled_time"] = None
        elif data.scheduled_time is not None:
            fields["scheduled_time"] = time.fromisoformat(data.scheduled_time)
        if data.clear_notes:
            fields["notes"] = None
        elif data.notes is not None:
            fields["notes"] = data.notes
        if not fields:
            raise NotFoundException(detail="Nothing to update")
        task = await task_service.update_task(task_id, **fields)
        if task is None:
            raise NotFoundException(detail=f"Task {task_id} not found")
        return _to_dto(task)

    @patch("/{task_id:int}/toggle")
    async def toggle_task(
        self,
        task_id: int,
        task_service: FromDishka[TaskService],
    ) -> TaskDTO:
        task = await task_service.toggle_task(task_id)
        if task is None:
            raise NotFoundException(detail=f"Task {task_id} not found")
        return _to_dto(task)

    @post("/{task_id:int}/backlog")
    async def move_to_backlog(
        self,
        task_id: int,
        task_service: FromDishka[TaskService],
    ) -> dict[str, bool]:
        ok = await task_service.move_to_backlog(task_id)
        if not ok:
            raise NotFoundException(detail=f"Task {task_id} not found")
        return {"ok": True}

    @post("/{task_id:int}/postpone")
    async def postpone_task(
        self,
        task_id: int,
        task_service: FromDishka[TaskService],
    ) -> TaskDTO:
        task = await task_service.postpone_task(task_id)
        if task is None:
            raise NotFoundException(detail=f"Task {task_id} not found")
        return _to_dto(task)

    @delete("/{task_id:int}")
    async def delete_task(
        self,
        task_id: int,
        task_service: FromDishka[TaskService],
    ) -> None:
        ok = await task_service.delete_task(task_id)
        if not ok:
            raise NotFoundException(detail=f"Task {task_id} not found")
