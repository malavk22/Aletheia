import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.routes import health
from app.core.db import get_db
from app.documents import embeddings, reranking
from app.main import app

client = TestClient(app)


@pytest.fixture
def models_loaded(monkeypatch):
    def set_loaded(embedder: bool, reranker: bool):
        monkeypatch.setattr(embeddings, "_model", FakeCache(embedder))
        monkeypatch.setattr(reranking, "_model", FakeCache(reranker))

    return set_loaded


class FakeCache:
    """Stands in for a model's lru_cache: only says whether it holds one."""

    def __init__(self, loaded: bool):
        self.loaded = loaded

    def cache_info(self):
        return type("Info", (), {"currsize": int(self.loaded)})()


def test_health_reports_database_and_models_ready(models_loaded):
    models_loaded(True, True)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "models": "ready"}


@pytest.mark.parametrize("embedder, reranker", [(False, False), (True, False), (False, True)])
def test_models_still_loading_is_reported_but_healthy(models_loaded, embedder, reranker):
    models_loaded(embedder, reranker)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["models"] == "loading"


class DownDatabase:
    def execute(self, statement):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def test_database_down_is_a_503_not_a_crash(models_loaded, monkeypatch):
    models_loaded(True, True)
    monkeypatch.setattr(health.logger, "disabled", False)
    app.dependency_overrides[get_db] = lambda: DownDatabase()
    try:
        response = client.get("/api/v1/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "down", "models": "ready"}
