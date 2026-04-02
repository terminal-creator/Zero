"""Task tools — in-memory task management (Create/Get/List/Update).

Corresponds to TS: tools/TaskCreateTool, TaskGetTool, TaskListTool, TaskUpdateTool.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from cc.tools.base import Tool, ToolResult, ToolSchema


@dataclass
class Task:
    """A tracked task."""

    id: str
    subject: str
    description: str = ""
    status: str = "pending"  # pending | in_progress | completed


class TaskStore:
    """In-memory task storage shared across all task tools."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def create(self, subject: str, description: str = "") -> Task:
        task = Task(id=str(uuid4())[:8], subject=subject, description=description)
        self._tasks[task.id] = task
        return task

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_all(self) -> list[Task]:
        return list(self._tasks.values())

    def update(self, task_id: str, **kwargs: Any) -> Task | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        return task


# Global store instance
_store = TaskStore()


def get_task_store() -> TaskStore:
    return _store


class TaskCreateTool(Tool):
    def __init__(self, store: TaskStore | None = None) -> None:
        self._store = store or _store

    def get_name(self) -> str:
        return "TaskCreate"

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="TaskCreate",
            description="Create a new task to track progress.",
            input_schema={
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Task title"},
                    "description": {"type": "string", "description": "Task details"},
                },
                "required": ["subject"],
            },
        )

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        subject = tool_input.get("subject", "")
        description = tool_input.get("description", "")
        if not subject:
            return ToolResult(content="Error: subject is required", is_error=True)
        task = self._store.create(subject, description)
        return ToolResult(content=f"Task #{task.id} created: {task.subject}")


class TaskGetTool(Tool):
    def __init__(self, store: TaskStore | None = None) -> None:
        self._store = store or _store

    def get_name(self) -> str:
        return "TaskGet"

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="TaskGet",
            description="Get details of a task by ID.",
            input_schema={
                "type": "object",
                "properties": {
                    "taskId": {"type": "string", "description": "Task ID"},
                },
                "required": ["taskId"],
            },
        )

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        task_id = tool_input.get("taskId", "")
        task = self._store.get(task_id)
        if task is None:
            return ToolResult(content=f"Error: Task {task_id} not found", is_error=True)
        return ToolResult(content=json.dumps({
            "id": task.id,
            "subject": task.subject,
            "description": task.description,
            "status": task.status,
        }))


class TaskListTool(Tool):
    def __init__(self, store: TaskStore | None = None) -> None:
        self._store = store or _store

    def get_name(self) -> str:
        return "TaskList"

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="TaskList",
            description="List all tasks.",
            input_schema={"type": "object", "properties": {}},
        )

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        tasks = self._store.list_all()
        if not tasks:
            return ToolResult(content="No tasks")
        lines = [f"#{t.id} [{t.status}] {t.subject}" for t in tasks]
        return ToolResult(content="\n".join(lines))


class TaskUpdateTool(Tool):
    def __init__(self, store: TaskStore | None = None) -> None:
        self._store = store or _store

    def get_name(self) -> str:
        return "TaskUpdate"

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="TaskUpdate",
            description="Update a task's status or details.",
            input_schema={
                "type": "object",
                "properties": {
                    "taskId": {"type": "string", "description": "Task ID"},
                    "status": {"type": "string", "description": "New status"},
                    "subject": {"type": "string", "description": "New subject"},
                },
                "required": ["taskId"],
            },
        )

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        task_id = tool_input.get("taskId", "")
        updates = {k: v for k, v in tool_input.items() if k != "taskId" and v is not None}
        task = self._store.update(task_id, **updates)
        if task is None:
            return ToolResult(content=f"Error: Task {task_id} not found", is_error=True)
        return ToolResult(content=f"Task #{task.id} updated: [{task.status}] {task.subject}")
