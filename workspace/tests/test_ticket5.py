import pytest
from httpx import ASGITransport, AsyncClient

from app.database import init_db
from app.crud import get_tasks
from app.main import app


@pytest.mark.asyncio
async def test_add_task_via_form(tmp_path, monkeypatch):
    custom_db = tmp_path / "test_form.db"
    monkeypatch.setenv("DATABASE_URL", str(custom_db))
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Ajout d'une tâche
        response = await client.post("/tasks", data={"title": "Nouvelle tâche test"})
        assert response.status_code == 303
        assert response.headers["location"] == "/"

        # Vérification en DB
        tasks = await get_tasks()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Nouvelle tâche test"


@pytest.mark.asyncio
async def test_toggle_task_via_form(tmp_path, monkeypatch):
    custom_db = tmp_path / "test_toggle.db"
    monkeypatch.setenv("DATABASE_URL", str(custom_db))
    await init_db()

    from app.crud import create_task
    await create_task("Tâche à basculer")
    tasks = await get_tasks()
    task_id = tasks[0]["id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(f"/tasks/{task_id}/toggle")
        assert response.status_code == 303

        tasks = await get_tasks()
        assert tasks[0]["completed"] == 1
