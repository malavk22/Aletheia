import uuid

import pytest
from docxs import make_docx
from pdfs import make_pdf
from test_documents import upload, workspace_for

from app.models.workspace import Workspace
from app.documents import reranking
from app.qa import llm
from app.services.qa import NOT_FOUND, PASSAGES, RERANK, _find_passages, _fuse, answer_question

# Passages are found with the fake embedder from conftest.py (shared words),
# and the model is a fake too: these tests check what Aletheia sends to the
# model and what it does with the reply, never the real Gemini.


@pytest.fixture
def fake_llm(monkeypatch):
    """Replaces Gemini with a fixed reply and remembers every call."""
    calls = []

    def install(reply):
        def generate(instructions, prompt):
            calls.append({"instructions": instructions, "prompt": prompt})
            if isinstance(reply, Exception):
                raise reply
            return reply

        monkeypatch.setattr(llm, "generate", generate)
        return calls

    return install


def workspace(db, workspace_id) -> Workspace:
    return db.get(Workspace, uuid.UUID(workspace_id))


def lease_workspace(client, db):
    workspace_id = workspace_for(client, "ada@example.com")
    content = make_pdf(
        "The tenant pays the rent monthly.",
        "Either party may terminate the lease with 30 days notice.",
    )
    upload(client, workspace_id, "lease.pdf", content)
    return workspace(db, workspace_id)


def test_answer_cites_the_passages_it_used(client, db, fake_llm):
    ada = lease_workspace(client, db)
    calls = fake_llm("Either party can end the lease with 30 days notice [1].")

    result = answer_question(db, ada, "terminate the lease with notice")

    assert result["answer"] == "Either party can end the lease with 30 days notice [1]."
    [citation] = result["citations"]
    assert citation["number"] == 1
    assert citation["filename"] == "lease.pdf"
    assert citation["page_number"] == 2
    assert "terminate the lease" in citation["text"]
    # The closest passage is sent first, as [1], with its place and the question.
    prompt = calls[0]["prompt"]
    assert prompt.index("[1] (lease.pdf, p. 2)") < prompt.index("[2] (lease.pdf, p. 1)")
    assert "terminate the lease with 30 days notice" in prompt
    assert prompt.endswith("Question: terminate the lease with notice")
    assert NOT_FOUND in calls[0]["instructions"]


def test_only_cited_passages_are_returned_in_number_order(client, db, fake_llm):
    ada = lease_workspace(client, db)
    fake_llm("Notice is 30 days [1]. Rent is paid monthly [2]. Again [1].")

    result = answer_question(db, ada, "terminate the lease with notice")

    assert [c["number"] for c in result["citations"]] == [1, 2]
    assert [c["page_number"] for c in result["citations"]] == [2, 1]


def test_invented_citations_are_removed(client, db, fake_llm):
    ada = lease_workspace(client, db)
    # Only 2 passages exist, so [9] and [0] point to nothing.
    fake_llm("Notice is 30 days [1][9]. Rent is monthly [0].")

    result = answer_question(db, ada, "terminate the lease")

    assert result["answer"] == "Notice is 30 days [1]. Rent is monthly."
    assert [c["number"] for c in result["citations"]] == [1]


def test_grouped_citations_are_split(client, db, fake_llm):
    ada = lease_workspace(client, db)
    fake_llm("Both pages cover the lease [1, 2].")

    result = answer_question(db, ada, "lease")

    assert result["answer"] == "Both pages cover the lease [1][2]."
    assert [c["number"] for c in result["citations"]] == [1, 2]


@pytest.mark.parametrize(
    "reply",
    [NOT_FOUND, "The lease is probably 12 months.", "Made up [7]."],
    ids=["model says not found", "no citation", "only invented citations"],
)
def test_answer_without_real_citations_is_not_found(client, db, fake_llm, reply):
    ada = lease_workspace(client, db)
    fake_llm(reply)

    result = answer_question(db, ada, "How long is the lease?")

    assert result == {"answer": NOT_FOUND, "citations": []}


def test_empty_workspace_does_not_call_the_model(client, db, fake_llm):
    ada = workspace(db, workspace_for(client, "ada@example.com"))
    calls = fake_llm("should not be used [1]")

    assert answer_question(db, ada, "rent?") == {"answer": NOT_FOUND, "citations": []}
    assert calls == []


def test_empty_reply_is_an_error(client, db, fake_llm):
    ada = lease_workspace(client, db)
    fake_llm("   ")

    with pytest.raises(llm.LLMError):
        answer_question(db, ada, "rent?")


def test_model_errors_are_passed_on(client, db, fake_llm):
    ada = lease_workspace(client, db)
    fake_llm(llm.LLMError("Gemini could not answer: 503"))

    with pytest.raises(llm.LLMError, match="503"):
        answer_question(db, ada, "rent?")


def test_at_most_PASSAGES_are_sent(client, db, fake_llm):
    workspace_id = workspace_for(client, "ada@example.com")
    content = make_pdf(*[f"Clause {n} about rent." for n in range(1, PASSAGES + 3)])
    upload(client, workspace_id, "lease.pdf", content)
    calls = fake_llm("Rent [1].")

    answer_question(db, workspace(db, workspace_id), "rent")

    prompt = calls[0]["prompt"]
    assert f"[{PASSAGES}] (" in prompt
    assert f"[{PASSAGES + 1}] (" not in prompt


def test_docx_passages_are_labelled_with_their_heading(client, db, fake_llm):
    workspace_id = workspace_for(client, "ada@example.com")
    content = make_docx(
        ("heading", "Termination"),
        ("p", "Either party may end the agreement."),
    )
    upload(client, workspace_id, "contract.docx", content)
    calls = fake_llm("It can be ended by either party [1].")

    result = answer_question(db, workspace(db, workspace_id), "end the agreement")

    assert "[1] (contract.docx, Termination)" in calls[0]["prompt"]
    assert result["citations"][0]["heading"] == "Termination"


def test_only_this_workspaces_passages_are_sent(client, db, fake_llm):
    bob_id = workspace_for(client, "bob@example.com")
    upload(client, bob_id, "bob.pdf", make_pdf("Bob's rent is secret."))
    ada_id = workspace_for(client, "ada@example.com")  # now signed in as Ada
    upload(client, ada_id, "ada.pdf", make_pdf("Ada pays the rent."))
    calls = fake_llm("Ada pays rent [1].")

    answer_question(db, workspace(db, ada_id), "rent")

    assert "ada.pdf" in calls[0]["prompt"]
    assert "bob.pdf" not in calls[0]["prompt"]
    assert "secret" not in calls[0]["prompt"]


def test_passages_with_rare_words_come_first(client, db, fake_llm):
    workspace_id = workspace_for(client, "ada@example.com")
    pages = [f"Chapter {n} of the project describes the project plan." for n in range(1, 6)]
    pages.append("The guide of this work is Mr Mer.")
    upload(client, workspace_id, "report.pdf", make_pdf(*pages))
    calls = fake_llm("The guide is Mr Mer [1].")

    result = answer_question(
        db, workspace(db, workspace_id), "who is the mentor/guide of the project"
    )

    # By meaning alone (shared words), the "project" pages are closer; the
    # page with the rare word "guide" still comes first, as [1].
    assert calls[0]["prompt"].startswith("Passages:\n\n[1] (report.pdf, p. 6)")
    assert result["citations"][0]["page_number"] == 6
    # The other places are filled by meaning, without repeating page 6.
    assert calls[0]["prompt"].count("(report.pdf, p. 6)") == 1
    assert "[6] (" in calls[0]["prompt"]


# POST /workspaces/{id}/ask — the route around answer_question.


def ask(client, workspace_id, question):
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/ask", json={"question": question}
    )


def test_ask_returns_the_answer_and_its_citations(client, db, fake_llm):
    ada = lease_workspace(client, db)
    fake_llm("Notice is 30 days [1].")

    response = ask(client, ada.id, "  terminate the lease with notice  ")

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Notice is 30 days [1]."
    [citation] = body["citations"]
    assert citation["number"] == 1
    assert (citation["filename"], citation["page_number"]) == ("lease.pdf", 2)
    assert "terminate the lease" in citation["text"]


def test_ask_trims_the_question(client, db, fake_llm):
    ada = lease_workspace(client, db)
    calls = fake_llm("Notice is 30 days [1].")

    ask(client, ada.id, "  terminate the lease  ")

    assert calls[0]["prompt"].endswith("Question: terminate the lease")


@pytest.mark.parametrize("question", ["", "   ", "x" * 501])
def test_ask_rejects_empty_or_too_long_questions(client, db, fake_llm, question):
    ada = lease_workspace(client, db)
    calls = fake_llm("unused [1]")

    assert ask(client, ada.id, question).status_code == 422
    assert calls == []


def test_ask_when_gemini_fails_is_503_with_a_plain_message(client, db, fake_llm):
    ada = lease_workspace(client, db)
    fake_llm(llm.LLMError("Gemini could not answer: 503 UNAVAILABLE model-x"))

    response = ask(client, ada.id, "rent?")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail == "Couldn't write an answer right now. Try again in a minute."
    # Google's raw message is logged, not shown.
    assert "model-x" not in detail


def test_ask_in_someone_elses_workspace_is_404(client, db, fake_llm):
    bob_id = workspace_for(client, "bob@example.com")
    workspace_for(client, "ada@example.com")  # now signed in as Ada
    calls = fake_llm("unused [1]")

    response = ask(client, bob_id, "rent?")

    assert response.status_code == 404
    assert calls == []


def test_ask_signed_out_is_401(client, db, fake_llm):
    ada = lease_workspace(client, db)
    client.post("/api/v1/auth/logout")
    calls = fake_llm("unused [1]")

    assert ask(client, ada.id, "rent?").status_code == 401
    assert calls == []


def ranked(*names, score=0.0):
    """A ranking of passages named by their chunk position, best first."""
    return [{"document_id": "doc", "chunk_position": name, "score": score} for name in names]


def test_a_passage_high_in_both_rankings_comes_first():
    by_words = ranked("a", "b", "c")
    by_meaning = ranked("c", "d", "a")

    # a: 1/61 + 1/63, c: 1/63 + 1/61 (equal, a seen first), then b, d.
    assert [p["chunk_position"] for p in _fuse(by_words, by_meaning)] == ["a", "c", "b", "d"]


def test_second_in_both_rankings_beats_first_in_only_one():
    by_words = ranked("only-words", "both")
    by_meaning = ranked("only-meaning", "both")

    assert _fuse(by_words, by_meaning)[0]["chunk_position"] == "both"


def test_fusion_uses_ranks_not_scores():
    # A huge keyword score must not outweigh a passage found by both.
    by_words = ranked("loud", "both", score=1000.0)
    by_meaning = ranked("quiet", "both", score=0.1)

    assert _fuse(by_words, by_meaning)[0]["chunk_position"] == "both"


def test_fused_passages_appear_once():
    fused = _fuse(ranked("a", "b"), ranked("b", "a"), ranked("a"))

    assert sorted(p["chunk_position"] for p in fused) == ["a", "b"]


def test_the_reranker_picks_the_final_passages(client, db, monkeypatch):
    workspace_id = workspace_for(client, "ada@example.com")
    pages = [f"Clause {n} about the rent." for n in range(1, 9)]
    upload(client, workspace_id, "lease.pdf", make_pdf(*pages))
    seen = []

    def relevance(question, texts):
        seen.append(texts)
        # Prefers clause 8, then 7, ...: the opposite of the fused order.
        return [float(text.split()[1]) for text in texts]

    monkeypatch.setattr(reranking, "relevance", relevance)

    passages = _find_passages(db, workspace(db, workspace_id), "clause about the rent")

    assert [p["page_number"] for p in passages] == [8, 7, 6, 5, 4, 3]
    # It read every fused candidate (up to RERANK), not only the first six.
    assert len(seen[0]) == min(8, RERANK)


def test_equal_reranker_scores_keep_the_fused_order(client, db, monkeypatch):
    workspace_id = workspace_for(client, "ada@example.com")
    upload(client, workspace_id, "lease.pdf", make_pdf(*[f"Clause {n} about the rent." for n in range(1, 9)]))
    fused_order = [p["page_number"] for p in _find_passages(db, workspace(db, workspace_id), "clause rent")]
    monkeypatch.setattr(reranking, "relevance", lambda question, texts: [0.0] * len(texts))

    passages = _find_passages(db, workspace(db, workspace_id), "clause rent")

    assert [p["page_number"] for p in passages] == fused_order


def test_nothing_found_means_no_reranking(client, db, monkeypatch):
    workspace_id = workspace_for(client, "ada@example.com")
    calls = []
    monkeypatch.setattr(reranking, "relevance", lambda question, texts: calls.append(texts) or [])

    assert _find_passages(db, workspace(db, workspace_id), "anything") == []
    assert calls == []
