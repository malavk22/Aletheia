"""Measures how fast the main endpoints answer (V1.0), with the real
embedding model and reranker on the check-set documents. Gemini is replaced
by an instant fake: its time is Google's, not Aletheia's.

Not collected by the normal test run; run it on purpose, from backend/:

    pytest tests/measure_speed.py -s
"""

import statistics
import time

from test_retrieval import check_workspaces, real_embeddings  # noqa: F401

from app.core import rate_limit
from app.documents import embeddings, reranking
from app.qa import llm

RUNS = 10


def timed(call) -> float:
    start = time.perf_counter()
    response = call()
    assert response.status_code == 200, response.text
    return (time.perf_counter() - start) * 1000


def test_measure_speed(client, db, real_embeddings, monkeypatch):
    monkeypatch.setattr(llm, "generate", lambda instructions, prompt: "Answer [1].")
    # Many more asks than the per-user limit allows, on purpose.
    monkeypatch.setattr(rate_limit.ai_requests, "limit", 1000)
    workspace = check_workspaces(client, db)
    base = f"/api/v1/workspaces/{workspace.id}"

    def search(mode):
        return lambda: client.get(f"{base}/search", params={"q": "notice period for contractors", "mode": mode})

    def ask(question):
        return lambda: client.post(f"{base}/ask", json={"question": question})

    # The first search with the models not yet loaded, as after a start
    # without loading them, then again once loaded.
    embeddings._model.cache_clear()
    reranking._model.cache_clear()
    cold_search = timed(search("semantic"))
    cold_ask = timed(ask("What is the late payment fee for rent?"))

    endpoints = {
        "health": lambda: client.get("/api/v1/health"),
        "document list": lambda: client.get(f"{base}/documents"),
        "search, meaning": search("semantic"),
        "search, exact words": search("keyword"),
        "ask, one part (no Gemini)": ask("What is the late payment fee for rent?"),
        "ask, two parts (no Gemini)": ask("How long is the notice period for employees, and for contractors?"),
    }
    print(f"\nFirst after start, models not loaded: search {cold_search:.0f} ms, then ask {cold_ask:.0f} ms")
    print(f"{'':30}{'median ms':>10}{'max ms':>10}")
    for name, call in endpoints.items():
        times = [timed(call) for _ in range(RUNS)]
        print(f"{name:30}{statistics.median(times):>10.0f}{max(times):>10.0f}")
