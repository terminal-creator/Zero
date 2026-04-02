"""Tests for Task tools.

Verifies T4.12: Create/Get/List/Update lifecycle.
"""

from cc.tools.task_tools.task_tools import (
    TaskCreateTool,
    TaskGetTool,
    TaskListTool,
    TaskStore,
    TaskUpdateTool,
)


class TestTaskTools:
    def _make_store(self) -> TaskStore:
        return TaskStore()

    async def test_create_and_get(self) -> None:
        store = self._make_store()
        create = TaskCreateTool(store)
        get = TaskGetTool(store)

        result = await create.execute({"subject": "Fix bug", "description": "In module X"})
        assert not result.is_error
        assert "Fix bug" in result.content

        # Extract task ID from result
        task_id = result.content.split("#")[1].split(" ")[0]
        get_result = await get.execute({"taskId": task_id})
        assert "Fix bug" in get_result.content
        assert "In module X" in get_result.content

    async def test_create_and_update(self) -> None:
        store = self._make_store()
        create = TaskCreateTool(store)
        update = TaskUpdateTool(store)
        get = TaskGetTool(store)

        result = await create.execute({"subject": "Write tests"})
        task_id = result.content.split("#")[1].split(" ")[0]

        update_result = await update.execute({"taskId": task_id, "status": "completed"})
        assert "completed" in update_result.content

        get_result = await get.execute({"taskId": task_id})
        assert "completed" in get_result.content

    async def test_list_multiple(self) -> None:
        store = self._make_store()
        create = TaskCreateTool(store)
        list_tool = TaskListTool(store)

        await create.execute({"subject": "Task A"})
        await create.execute({"subject": "Task B"})
        await create.execute({"subject": "Task C"})

        result = await list_tool.execute({})
        assert "Task A" in result.content
        assert "Task B" in result.content
        assert "Task C" in result.content

    async def test_get_nonexistent(self) -> None:
        store = self._make_store()
        get = TaskGetTool(store)
        result = await get.execute({"taskId": "nonexistent"})
        assert result.is_error

    async def test_empty_subject_error(self) -> None:
        store = self._make_store()
        create = TaskCreateTool(store)
        result = await create.execute({"subject": ""})
        assert result.is_error

    async def test_list_empty(self) -> None:
        store = self._make_store()
        list_tool = TaskListTool(store)
        result = await list_tool.execute({})
        assert "No tasks" in result.content
