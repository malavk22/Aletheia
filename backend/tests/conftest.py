import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.db import engine, get_db
from app.main import app


@pytest.fixture
def db():
    # Each test runs inside one transaction that is rolled back at the end,
    # so tests never leave rows in the database. "create_savepoint" lets the
    # app code call commit() without ending that outer transaction.
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()
