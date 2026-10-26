import threading

from fastapi.testclient import TestClient

from app import main
from app.documents import embeddings, reranking


def test_load_models_uses_both_models(monkeypatch):
    used = []
    monkeypatch.setattr(embeddings, "embed_query", lambda text: used.append("embeddings"))
    monkeypatch.setattr(reranking, "relevance", lambda question, texts: used.append("reranker"))

    main.load_models()

    assert used == ["embeddings", "reranker"]


def test_a_model_that_fails_to_load_doesnt_stop_the_server(monkeypatch, caplog):
    def offline(text):
        raise OSError("no internet")

    monkeypatch.setattr(embeddings, "embed_query", offline)
    # The test run's migrations (alembic.ini's logging setup) switch off
    # loggers that already exist; the app itself never runs them.
    monkeypatch.setattr(main.logger, "disabled", False)

    main.load_models()  # doesn't raise

    assert "will load on first use" in caplog.text


def test_starting_the_app_loads_the_models_in_the_background(monkeypatch):
    loaded = threading.Event()
    monkeypatch.setattr(main, "load_models", loaded.set)

    # Entering the client runs the app's start-up.
    with TestClient(main.app) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert loaded.wait(timeout=5)
