import os
import pytest
from app.database import DB_PATH, get_db_path, init_db


@pytest.mark.asyncio
async def test_init_db_creates_file_and_table(tmp_path, monkeypatch):
    custom_db = tmp_path / "custom_todo.db"
    monkeypatch.setenv("DATABASE_URL", str(custom_db))

    assert not custom_db.exists()
    await init_db()
    assert custom_db.exists()

    # Vérification que la table tasks existe et est utilisable
    import aiosqlite
    async with aiosqlite.connect(str(custom_db)) as db:
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks';")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "tasks"


@pytest.mark.asyncio
async def test_init_db_default_creates_db():
    db_path = get_db_path()
    await init_db()
    assert os.path.exists(db_path)
