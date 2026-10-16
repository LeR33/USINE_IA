import pytest
from httpx import ASGITransport, AsyncClient

from app.database import init_db
from app.crud import create_task
from app.main import app


@pytest.mark.asyncio
async def test_root_renders_template_with_tasks(tmp_path, monkeypatch):
    custom_db = tmp_path / "test_ui.db"
    monkeypatch.setenv("DATABASE_URL", str(custom_db))
    await init_db()

    await create_task("Apprendre Jinja2")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Ma Liste de Tâches" in response.text
    assert "Apprendre Jinja2" in response.text
