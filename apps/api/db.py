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
from sqlalchemy.pool import NullPool

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

# Supabase's pooled connection string (port 6543, PgBouncer in "transaction"
# mode — see .env.example) routes each query to a possibly-different backend
# connection, so psycopg's default server-side prepared statements (which
# assume a stable connection) break with "prepared statement already exists"
# errors. Disabling them is the documented fix and a no-op cost-wise for our
# query volume. NullPool avoids holding a SQLAlchemy-level pool open inside
# a serverless function instance, which is redundant when PgBouncer already
# pools in front of it — direct/local connections (port 5432 or SQLite)
# don't need either and keep the default pool.
_uses_pgbouncer = ":6543" in DATABASE_URL

connect_args: dict[str, object] = {}
engine_kwargs: dict[str, object] = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif _uses_pgbouncer:
    connect_args = {"prepare_threshold": None}
    engine_kwargs = {"poolclass": NullPool}

engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
