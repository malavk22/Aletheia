import uuid

import pytest
from docxs import make_docx
from pdfs import make_pdf
from test_documents import upload, workspace_for

from app.models.workspace import Workspace
from app.qa import llm
from app.services.qa import NOT_FOUND, PASSAGES, answer_question

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
