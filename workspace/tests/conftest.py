import os
import tempfile
from pathlib import Path

# Base temporaire AVANT l'import de l'app
_tmp = tempfile.mkdtemp()
os.environ["FROIDPRO_DB"] = str(Path(_tmp) / "test.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine, init_db  # noqa: E402
from app.main import UPLOADS, app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True, scope="session")
def cleanup_uploads():
    before = set(UPLOADS.glob("logo-*"))
    yield
    for f in set(UPLOADS.glob("logo-*")) - before:
        f.unlink(missing_ok=True)


# ---- helpers ----
from datetime import date  # noqa: E402

from app import services  # noqa: E402


def make_client(db, nom="Dupont SARL", **kw):
    return services.create_client(db, {"nom": nom, **kw})


def make_itv(db, client_id, jour=None, lignes=True, **kw):
    data = {"client_id": client_id, "date": (jour or date.today()).isoformat(), "heure_debut": "09:00",
            "heure_fin": "11:00", "type": "Dépannage", "technicien": "Paul", **kw}
    if lignes:
        data = {"ligne_designation": ["Main d'oeuvre", "Gaz R32"], "ligne_quantite": ["2", "1"],
                "ligne_prix": ["50", "80"], "ligne_tva": ["20", "20"], **data}
    return services.create_intervention(db, data)
