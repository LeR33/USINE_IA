import pytest
from app.database import init_db
from app.crud import create_task, get_tasks, toggle_task

@pytest.mark.asyncio
async def test_crud_tasks(tmp_path, monkeypatch):
    custom_db = tmp_path / "test_crud.db"
    monkeypatch.setenv("DATABASE_URL", str(custom_db))
    await init_db()

    tasks = await get_tasks()
    assert tasks == []

    await create_task("Acheter du pain")
    tasks = await get_tasks()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Acheter du pain"
    assert tasks[0]["completed"] == 0

    task_id = tasks[0]["id"]
    await toggle_task(task_id)
    tasks = await get_tasks()
    assert tasks[0]["completed"] == 1
