"""Connexion SQLite. DATABASE_URL peut être surchargée (tests : base temporaire)."""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("FROIDPRO_DB", BASE_DIR / "data" / "froidpro.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    """Crée les tables et les paramètres par défaut s'ils n'existent pas."""
    from app import models  # noqa: F401  (enregistre les modèles)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.Parametres).first() is None:
            db.add(models.Parametres())
            db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
