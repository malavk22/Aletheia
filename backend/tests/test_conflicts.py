from pdfs import make_pdf
from test_documents import upload, workspace_for
from test_facts import fake_gemini_json  # noqa: F401 (a fixture, used by name)

from app.qa import llm

# Two made-up documents that disagree on the notice period. Each page is short,
# so each page is one chunk.
CONTRACT = (
    "The tenant must give 30 days notice before leaving.",
    "Rent is paid on the first day of each month.",
)
POLICY = (
    "Tenants must give 60 days notice before leaving.",
    "The office is open from 9 to 5 on weekdays.",
)

NOTICE_A = "The tenant must give 30 days notice before leaving."
NOTICE_B = "Tenants must give 60 days notice before leaving."


def two_documents(client, a_pages=CONTRACT, b_pages=POLICY):
    workspace_id = workspace_for(client, "ada@example.com")
    a_id, b_id = (
        upload(client, workspace_id, name, make_pdf(*pages)).json()["id"]
        for name, pages in (("contract.pdf", a_pages), ("policy.pdf", b_pages))
    )
    return workspace_id, a_id, b_id


def check(client, workspace_id, a_id, b_id):
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/compare/conflicts",
        json={"document_a": a_id, "document_b": b_id},
    )


def conflict(**fields):
    return {
        "pair": 1,
        "topic": "notice period",
        "claim_a": "30 days notice",
        "quote_a": NOTICE_A,
        "claim_b": "60 days notice",
        "quote_b": NOTICE_B,
        "explanation": "The notice period can't be both 30 and 60 days.",
        **fields,
    }


def test_a_conflict_is_returned_with_both_quotes_and_pages(client, fake_gemini_json):
    workspace_id, a_id, b_id = two_documents(client)
    fake_gemini_json({"conflicts": [conflict()]})

    response = check(client, workspace_id, a_id, b_id)

    assert response.status_code == 200
    body = response.json()
    assert (body["checked_pairs"], body["dropped"]) == (2, 0)
    [found] = body["potential_conflicts"]
    assert found["topic"] == "notice period"
    assert found["a"] == {
        "claim": "30 days notice",
        "quote": NOTICE_A,
        "part_position": 1,
        "page_number": 1,
        "heading": None,
    }
    assert (found["b"]["quote"], found["b"]["page_number"]) == (NOTICE_B, 1)


def test_the_most_alike_passages_are_paired_and_sent(client, fake_gemini_json):
    workspace_id, a_id, b_id = two_documents(client)
    calls = fake_gemini_json({"conflicts": []})

    check(client, workspace_id, a_id, b_id)

    prompt = calls[0]["prompt"]
    assert prompt.startswith("Document A: contract.pdf\nDocument B: policy.pdf")
    # The two notice passages share the most words: they are pair 1.
    assert f"[pair 1]\nA (p. 1): {NOTICE_A}\nB (p. 1): {NOTICE_B}" in prompt
    assert "[pair 2]" in prompt and "[pair 3]" not in prompt
    assert "cannot both be true" in calls[0]["instructions"]


def test_a_conflict_is_dropped_unless_each_quote_is_in_its_own_passage(
    client, fake_gemini_json
):
    workspace_id, a_id, b_id = two_documents(client)
    fake_gemini_json(
        {
            "conflicts": [
                # Quotes swapped: each is real, but in the other document.
                conflict(quote_a=NOTICE_B, quote_b=NOTICE_A),
                # A quote that isn't in the documents at all, on either side.
                conflict(quote_a="The tenant must give 90 days notice."),
                conflict(quote_b="Tenants must give 90 days notice."),
                # Pair numbers that don't exist; True is not a pair number.
                conflict(pair=3),
                conflict(pair=0),
                conflict(pair=True, topic="pair True"),
                conflict(quote_a=""),
                # The one real conflict, given twice: kept once.
                conflict(),
                conflict(topic="notice"),
            ]
        }
    )

    body = check(client, workspace_id, a_id, b_id).json()

    assert [found["topic"] for found in body["potential_conflicts"]] == ["notice period"]
    assert body["dropped"] == 8


def test_a_quote_is_found_despite_line_breaks_and_capitals(client, fake_gemini_json):
    workspace_id, a_id, b_id = two_documents(client)
    fake_gemini_json(
        {"conflicts": [conflict(quote_a="the tenant must give 30 days\nnotice before leaving.")]}
    )

    body = check(client, workspace_id, a_id, b_id).json()

    assert len(body["potential_conflicts"]) == 1


def test_identical_passages_are_not_sent(client, fake_gemini_json):
    # Same text in both: nothing to contradict, so Gemini isn't called.
    workspace_id, a_id, b_id = two_documents(client, CONTRACT, CONTRACT)
    calls = fake_gemini_json()

    body = check(client, workspace_id, a_id, b_id).json()

    assert body == {"potential_conflicts": [], "checked_pairs": 0, "dropped": 0}
    assert calls == []


def test_each_passage_is_in_at_most_one_pair(client, fake_gemini_json):
    # B has one page, so only one pair can be made.
    workspace_id, a_id, b_id = two_documents(client, CONTRACT, POLICY[:1])
    calls = fake_gemini_json({"conflicts": []})

    body = check(client, workspace_id, a_id, b_id).json()

    assert body["checked_pairs"] == 1
    assert calls[0]["prompt"].count(NOTICE_B) == 1


def test_when_gemini_fails_the_answer_is_503(client, fake_gemini_json):
    workspace_id, a_id, b_id = two_documents(client)
    fake_gemini_json(llm.LLMError("Gemini could not answer: 503 model-x"))

    response = check(client, workspace_id, a_id, b_id)

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail == "Couldn't check for conflicts right now. Try again in a minute."
    assert "model-x" not in detail


def test_nothing_is_sent_when_the_documents_cant_be_compared(client, fake_gemini_json):
    workspace_id, a_id, b_id = two_documents(client)
    failed_id = upload(client, workspace_id, "scan.pdf", make_pdf("")).json()["id"]
    calls = fake_gemini_json()

    assert check(client, workspace_id, a_id, a_id).status_code == 422
    assert check(client, workspace_id, a_id, failed_id).status_code == 409
    workspace_for(client, "bob@example.com")  # now signed in as Bob
    assert check(client, workspace_id, a_id, b_id).status_code == 404
    client.post("/api/v1/auth/logout")
    assert check(client, workspace_id, a_id, b_id).status_code == 401
    assert calls == []
