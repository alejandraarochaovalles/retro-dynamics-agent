# SQLAlchemy engine/session setup.
#
# Falls back to a local SQLite file when DATABASE_URL isn't set, so the app
# still boots with zero config (same philosophy as config.py's other
# integrations) — set DATABASE_URL (see .env.example) to point at real
# Postgres. Schema is managed by Alembic (see alembic/), not by
# create_all(); run `alembic upgrade head` before starting the app.
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings


def resolve_database_url() -> str:
    url = settings.database_url
    if not url:
        return "sqlite:///./dev.db"
    # .env.example documents the plain "postgresql://" scheme; SQLAlchemy
    # needs the driver spelled out to pick psycopg (v3) over psycopg2.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = resolve_database_url()

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
