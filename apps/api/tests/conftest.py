# Points the app at a dedicated Postgres test database (not the dev one —
# tests truncate tables between runs) and overrides get_db so routes use
# it instead of whatever DATABASE_URL is set to in the caller's shell.
# Override TEST_DATABASE_URL if your local Postgres uses different
# credentials than .env.example's.
from __future__ import annotations

import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://user:password@localhost:5432/retro_dynamics_test"
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import db_models  # noqa: F401  (registers tables on Base.metadata)
from db import DATABASE_URL, Base, get_db
from main import app

engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    with engine.begin() as conn:
        for table in ("action_items", "sessions", "teams"):
            conn.exec_driver_sql(f"DELETE FROM {table}")
    yield


def _override_get_db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def db_session():
    """A DB session independent of the app's — for asserting a row really
    made it to Postgres rather than just trusting the app's own response."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
