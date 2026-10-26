import logging
import re

import pytest
from test_documents import workspace_for

from app import main
from app.api.routes import workspaces


@pytest.fixture
def request_log(monkeypatch, caplog):
    # The test run's migrations (alembic.ini's logging setup) switch off
    # loggers that already exist; the app itself never runs them.
    monkeypatch.setattr(main.request_logger, "disabled", False)
    caplog.set_level(logging.DEBUG, logger="app.requests")
    return caplog


def lines(caplog):
    return [record.getMessage() for record in caplog.records if record.name == "app.requests"]


def test_each_request_is_logged_with_status_time_and_id(client, request_log):
    response = client.get("/api/v1/auth/me")

    request_id = response.headers["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f]{8}", request_id)
    [line] = lines(request_log)
    assert re.fullmatch(rf"GET /api/v1/auth/me 401 \d+ ms \[{request_id}\]", line)


def test_every_request_gets_its_own_id(client):
    first = client.get("/api/v1/auth/me").headers["X-Request-ID"]
    second = client.get("/api/v1/auth/me").headers["X-Request-ID"]

    assert first != second


def test_what_was_searched_is_not_logged(client, request_log):
    workspace_id = workspace_for(client, "ada@example.com")
    request_log.clear()

    client.get(f"/api/v1/workspaces/{workspace_id}/search", params={"q": "salary of Ada Lovelace"})

    [line] = lines(request_log)
    assert f"GET /api/v1/workspaces/{workspace_id}/search 200" in line
    assert "salary" not in line


def test_health_is_logged_only_when_looking_closely(client, request_log):
    client.get("/api/v1/health")

    [record] = [r for r in request_log.records if r.name == "app.requests"]
    assert record.levelno == logging.DEBUG


def test_a_bug_is_logged_with_its_id_and_answered_with_a_plain_500(client, request_log, monkeypatch):
    workspace_for(client, "ada@example.com")
    request_log.clear()

    def broken(db, user):
        raise RuntimeError("a bug")

    monkeypatch.setattr(workspaces, "list_workspaces", broken)

    response = client.get("/api/v1/workspaces")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}
    request_id = response.headers["X-Request-ID"]
    [record] = [r for r in request_log.records if r.name == "app.requests"]
    assert record.levelno == logging.ERROR
    assert "GET /api/v1/workspaces failed after" in record.getMessage()
    assert f"[{request_id}]" in record.getMessage()
    assert "RuntimeError: a bug" in request_log.text
    # The security headers still wrap the error reply.
    assert response.headers["X-Frame-Options"] == "DENY"
