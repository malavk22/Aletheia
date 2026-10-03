from contextlib import nullcontext
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings

# Tests use their own database, never the development one. We take the normal
# address from .env and swap only the database name. This must happen before
# anything imports app.core.db, because that is where the engine is created.
TEST_DATABASE = "aletheia_test"
dev_url = make_url(settings.database_url)
settings.database_url = dev_url.set(database=TEST_DATABASE).render_as_string(
    hide_password=False
)

from app.core.db import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import documents as documents_service  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def test_database():
    # Safety check: refuse to run if the engine points anywhere else.
    assert engine.url.database == TEST_DATABASE

    # Once per test run: create the test database if it is missing...
    admin = create_engine(dev_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        exists = connection.scalar(
            text("select 1 from pg_database where datname = :name"),
            {"name": TEST_DATABASE},
        )
        if not exists:
            connection.execute(text(f'create database "{TEST_DATABASE}"'))
    admin.dispose()

    # ...and build its tables with the real migrations, which also proves the
    # migrations work from an empty database.
    alembic_ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    command.upgrade(Config(str(alembic_ini)), "head")


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    # Every test gets its own empty, temporary upload folder, so no test can
    # ever write into the real uploads folder.
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def db():
    # Each test runs inside one transaction that is rolled back at the end,
    # so tests never leave rows behind. "create_savepoint" lets the app code
    # call commit() without ending that outer transaction.
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db
    # Background jobs open their own session in real use. In tests they must
    # use the test's session, or they could not see rows the test created
    # (those are never committed for real) and would leave data behind.
    monkeypatch.setattr(documents_service, "open_session", lambda: nullcontext(db))
    yield TestClient(app)
    app.dependency_overrides.clear()
