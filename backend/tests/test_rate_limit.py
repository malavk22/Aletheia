import pytest
from pdfs import make_pdf
from test_documents import upload, workspace_for

from app.core.rate_limit import RateLimiter
from app.qa import llm


class Clock:
    """A clock the test moves by hand."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


# The limiter itself.


def test_events_up_to_the_limit_are_allowed_then_blocked():
    clock = Clock()
    limiter = RateLimiter(limit=3, window=60, clock=clock)

    assert [limiter.hit("ada") for _ in range(3)] == [None, None, None]
    assert limiter.hit("ada") == 60


def test_the_wait_counts_down_from_the_oldest_event():
    clock = Clock()
    limiter = RateLimiter(limit=2, window=60, clock=clock)
    limiter.hit("ada")
    clock.now += 20
    limiter.hit("ada")

    clock.now += 10
    # The first event is forgotten 60 s after it happened: 30 s from now.
    assert limiter.retry_after("ada") == 30


def test_old_events_are_forgotten_after_the_window():
    clock = Clock()
    limiter = RateLimiter(limit=2, window=60, clock=clock)
    limiter.hit("ada")
    limiter.hit("ada")

    clock.now += 60

    assert limiter.hit("ada") is None


def test_a_blocked_attempt_is_not_counted():
    # Otherwise someone who keeps trying would never be let back in.
    clock = Clock()
    limiter = RateLimiter(limit=1, window=60, clock=clock)
    limiter.hit("ada")
    clock.now += 30
    assert limiter.hit("ada") == 30

    clock.now += 30

    assert limiter.hit("ada") is None


def test_keys_are_counted_apart():
    limiter = RateLimiter(limit=1, window=60, clock=Clock())
    limiter.hit("ada")

    assert limiter.hit("bob") is None


def test_idle_keys_are_forgotten():
    clock = Clock()
    limiter = RateLimiter(limit=1, window=60, clock=clock)
    limiter.hit("ada")
    clock.now += 61

    assert limiter.retry_after("ada") is None
    assert limiter.events == {}


def test_many_idle_keys_are_cleared_when_the_table_is_full(monkeypatch):
    monkeypatch.setattr("app.core.rate_limit.MAX_KEYS", 3)
    clock = Clock()
    limiter = RateLimiter(limit=5, window=60, clock=clock)
    for address in ["a", "b", "c", "d"]:
        limiter.hit(address)
    clock.now += 61

    limiter.hit("e")

    assert set(limiter.events) == {"e"}


# Signing in and signing up.


def login(client, password):
    return client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": password})


def test_five_failed_sign_ins_block_the_sixth_even_with_the_right_password(client):
    client.post("/api/v1/auth/register", json={"email": "ada@example.com", "password": "correct-horse"})
    for _ in range(5):
        assert login(client, "wrong-horse").status_code == 401

    response = login(client, "correct-horse")

    assert response.status_code == 429
    assert response.json()["detail"] == "Too many failed sign-in attempts. Try again in about 15 minutes."
    assert response.headers["Retry-After"] == "900"


def test_successful_sign_ins_are_not_counted(client):
    client.post("/api/v1/auth/register", json={"email": "ada@example.com", "password": "correct-horse"})
    for _ in range(6):
        assert login(client, "correct-horse").status_code == 200


def test_too_many_new_accounts_from_one_address_are_refused(client):
    for n in range(10):
        response = client.post("/api/v1/auth/register", json={"email": f"user{n}@example.com", "password": "correct-horse"})
        assert response.status_code == 201

    response = client.post("/api/v1/auth/register", json={"email": "user10@example.com", "password": "correct-horse"})

    assert response.status_code == 429
    assert response.json()["detail"] == "Too many new accounts from this address. Try again in about 1 hour."


# AI requests.


@pytest.fixture
def gemini_answers(monkeypatch):
    calls = []

    def generate(instructions, prompt):
        calls.append(prompt)
        return "Rent is monthly [1]."

    monkeypatch.setattr(llm, "generate", generate)
    return calls


def ask(client, workspace_id):
    return client.post(f"/api/v1/workspaces/{workspace_id}/ask", json={"question": "rent"})


def test_the_eleventh_ai_request_in_a_minute_is_refused_without_calling_gemini(client, gemini_answers):
    workspace_id = workspace_for(client, "ada@example.com")
    upload(client, workspace_id, "lease.pdf", make_pdf("The rent is paid monthly."))
    for _ in range(10):
        assert ask(client, workspace_id).status_code == 200

    response = ask(client, workspace_id)

    assert response.status_code == 429
    assert response.json()["detail"] == "Too many AI requests. Try again in about a minute."
    assert len(gemini_answers) == 10


def test_ai_requests_are_counted_per_user(client, gemini_answers):
    ada = workspace_for(client, "ada@example.com")
    upload(client, ada, "lease.pdf", make_pdf("The rent is paid monthly."))
    for _ in range(10):
        ask(client, ada)
    bob = workspace_for(client, "bob@example.com")  # now signed in as Bob
    upload(client, bob, "lease.pdf", make_pdf("The rent is paid monthly."))

    assert ask(client, bob).status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/workspaces/{ws}/documents/{doc}/facts",
        "/api/v1/workspaces/{ws}/documents/{doc}/actions",
    ],
)
def test_extraction_routes_share_the_ai_limit(client, gemini_answers, path):
    workspace_id = workspace_for(client, "ada@example.com")
    document_id = upload(client, workspace_id, "lease.pdf", make_pdf("The rent is paid monthly.")).json()["id"]
    for _ in range(10):
        ask(client, workspace_id)

    response = client.post(path.format(ws=workspace_id, doc=document_id))

    assert response.status_code == 429


def test_the_conflict_check_shares_the_ai_limit(client, gemini_answers):
    workspace_id = workspace_for(client, "ada@example.com")
    a = upload(client, workspace_id, "a.pdf", make_pdf("The rent is paid monthly.")).json()["id"]
    b = upload(client, workspace_id, "b.pdf", make_pdf("The rent is paid weekly.")).json()["id"]
    for _ in range(10):
        ask(client, workspace_id)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/compare/conflicts", json={"document_a": a, "document_b": b}
    )

    assert response.status_code == 429


def test_searching_is_not_limited(client, gemini_answers):
    workspace_id = workspace_for(client, "ada@example.com")
    upload(client, workspace_id, "lease.pdf", make_pdf("The rent is paid monthly."))
    for _ in range(10):
        ask(client, workspace_id)

    response = client.get(f"/api/v1/workspaces/{workspace_id}/search", params={"q": "rent"})

    assert response.status_code == 200


# Security headers.


@pytest.mark.parametrize("path", ["/api/v1/health", "/api/v1/auth/me", "/api/v1/no-such-page"])
def test_every_response_carries_the_security_headers(client, path):
    headers = client.get(path).headers

    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Content-Security-Policy"] == "frame-ancestors 'none'"
    assert headers["Referrer-Policy"] == "same-origin"
