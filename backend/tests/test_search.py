import uuid

import pytest

from docxs import make_docx
from pdfs import make_pdf
from test_documents import upload, workspace_for

from app.models.workspace import Workspace
from app.services.search import rare_word_search

# Tests use the fake embedder from conftest.py, which only counts shared
# words, so "closest" here means "shares the most words with the question".
# tests/test_embeddings.py checks that the real model matches by meaning.


def search_url(workspace_id):
    return f"/api/v1/workspaces/{workspace_id}/search"


def search(client, workspace_id, q, **params):
    return client.get(search_url(workspace_id), params={"q": q, **params})


def test_closest_chunk_comes_first_with_its_document_and_page(client):
    workspace_id = workspace_for(client, "ada@example.com")
    content = make_pdf(
        "The tenant pays the rent monthly.",
        "Either party may terminate the lease with notice.",
    )
    document_id = upload(client, workspace_id, "lease.pdf", content).json()["id"]

    response = search(client, workspace_id, "terminate the lease with notice")
    results = response.json()

    assert response.status_code == 200
    assert len(results) == 2
    best = results[0]
    assert best["document_id"] == document_id
    assert best["filename"] == "lease.pdf"
    assert best["page_number"] == 2
    assert best["part_position"] == 2
    assert best["source"] == "text"
    assert "terminate the lease" in best["text"]
    assert best["score"] > results[1]["score"]
    assert best["score"] <= 1


def test_docx_results_carry_their_heading(client):
    workspace_id = workspace_for(client, "ada@example.com")
    content = make_docx(
        ("heading", "Payment"),
        ("p", "Invoices are paid within 30 days."),
        ("heading", "Termination"),
        ("p", "Either party may end the agreement."),
    )
    upload(client, workspace_id, "contract.docx", content)

    best = search(client, workspace_id, "end the agreement").json()[0]

    assert (best["heading"], best["page_number"]) == ("Termination", None)


def test_search_only_finds_documents_in_that_workspace(client):
    bob_workspace = workspace_for(client, "bob@example.com")
    upload(client, bob_workspace, "bob.pdf", make_pdf("Bob's rent is secret."))
    ada_workspace = workspace_for(client, "ada@example.com")  # now signed in as Ada
    upload(client, ada_workspace, "ada.pdf", make_pdf("Ada pays the rent."))

    results = search(client, ada_workspace, "rent").json()

    assert [result["filename"] for result in results] == ["ada.pdf"]


def test_limit_caps_the_number_of_results(client):
    workspace_id = workspace_for(client, "ada@example.com")
    content = make_pdf(*[f"Clause {n} about rent." for n in range(1, 6)])
    upload(client, workspace_id, "lease.pdf", content)

    assert len(search(client, workspace_id, "rent", limit=3).json()) == 3
    assert len(search(client, workspace_id, "rent").json()) == 5


def test_workspace_without_documents_gives_no_results(client):
    workspace_id = workspace_for(client, "ada@example.com")

    assert search(client, workspace_id, "rent").json() == []


def test_empty_question_is_rejected(client):
    workspace_id = workspace_for(client, "ada@example.com")

    assert search(client, workspace_id, "   ").status_code == 422
    assert search(client, workspace_id, "x" * 501).status_code == 422
    assert search(client, workspace_id, "rent", limit=0).status_code == 422


def test_other_users_cannot_search_my_workspace(client):
    workspace_id = workspace_for(client, "ada@example.com")
    upload(client, workspace_id, "lease.pdf", make_pdf("Ada pays the rent."))

    workspace_for(client, "bob@example.com")  # now signed in as Bob
    response = search(client, workspace_id, "rent")

    assert response.status_code == 404


def test_search_requires_login(client):
    workspace_id = workspace_for(client, "ada@example.com")
    client.post("/api/v1/auth/logout")

    assert search(client, workspace_id, "rent").status_code == 401


def keyword(client, workspace_id, q, **params):
    return search(client, workspace_id, q, mode="keyword", **params)


def test_keyword_search_returns_only_chunks_with_the_words(client):
    workspace_id = workspace_for(client, "ada@example.com")
    content = make_pdf("The deposit is 1000.", "The rent is 500.", "Pets are allowed.")
    upload(client, workspace_id, "lease.pdf", content)

    results = keyword(client, workspace_id, "deposit").json()

    assert [(r["page_number"], r["text"]) for r in results] == [(1, "The deposit is 1000.")]


def test_keyword_search_matches_other_forms_of_a_word(client):
    workspace_id = workspace_for(client, "ada@example.com")
    upload(client, workspace_id, "lease.pdf", make_pdf("The lease was terminated early."))

    results = keyword(client, workspace_id, "termination").json()

    assert len(results) == 1


def test_keyword_search_finds_exact_codes(client):
    workspace_id = workspace_for(client, "ada@example.com")
    content = make_pdf("Invoice INV-20391 is overdue.", "Invoice INV-55555 is paid.")
    upload(client, workspace_id, "invoices.pdf", content)

    results = keyword(client, workspace_id, "INV-20391").json()

    assert [r["page_number"] for r in results] == [1]


def test_keyword_search_understands_phrases_and_exclusions(client):
    workspace_id = workspace_for(client, "ada@example.com")
    content = make_pdf(
        "A late fee applies after 5 days.",
        "The fee is never late.",
        "A late fee applies to pets too.",
    )
    upload(client, workspace_id, "lease.pdf", content)

    phrase = keyword(client, workspace_id, '"late fee"').json()
    excluded = keyword(client, workspace_id, '"late fee" -pets').json()

    assert sorted(r["page_number"] for r in phrase) == [1, 3]
    assert [r["page_number"] for r in excluded] == [1]


def test_keyword_search_ranks_more_mentions_higher(client):
    workspace_id = workspace_for(client, "ada@example.com")
    content = make_pdf(
        "Rent is due monthly.", "Rent is due monthly. Late rent costs extra rent."
    )
    upload(client, workspace_id, "lease.pdf", content)

    results = keyword(client, workspace_id, "rent").json()

    assert [r["page_number"] for r in results] == [2, 1]
    assert results[0]["score"] > results[1]["score"]


def test_keyword_search_with_only_common_words_finds_nothing(client):
    workspace_id = workspace_for(client, "ada@example.com")
    upload(client, workspace_id, "lease.pdf", make_pdf("The rent is due."))

    assert keyword(client, workspace_id, "the is").json() == []


def test_keyword_search_only_finds_documents_in_that_workspace(client):
    bob_workspace = workspace_for(client, "bob@example.com")
    upload(client, bob_workspace, "bob.pdf", make_pdf("Bob's rent is secret."))
    ada_workspace = workspace_for(client, "ada@example.com")  # now signed in as Ada
    upload(client, ada_workspace, "ada.pdf", make_pdf("Ada pays the rent."))

    results = keyword(client, ada_workspace, "rent").json()

    assert [result["filename"] for result in results] == ["ada.pdf"]


def test_unknown_search_mode_is_rejected(client):
    workspace_id = workspace_for(client, "ada@example.com")

    assert search(client, workspace_id, "rent", mode="magic").status_code == 422


# rare_word_search is used by Ask (V0.4), not by the search box, so these
# tests call it directly.


def report_workspace(client, db):
    """A report where "project" is everywhere and "guide" on one page."""
    workspace_id = workspace_for(client, "ada@example.com")
    pages = [f"Chapter {n} of the project describes the project plan." for n in range(1, 6)]
    pages.append("The guide of this work is Mr Mer.")
    upload(client, workspace_id, "report.pdf", make_pdf(*pages))
    return db.get(Workspace, uuid.UUID(workspace_id))


def test_rare_word_search_ignores_words_found_everywhere(client, db):
    report = report_workspace(client, db)

    # "project" is in 5 of 6 chunks, so only "guide" is searched for, and
    # "mentor", which no document contains, does not block it.
    results = rare_word_search(db, report, "who is the mentor/guide of the project", 10)

    assert [result["page_number"] for result in results] == [6]


def test_rare_word_search_with_only_common_words_finds_nothing(client, db):
    report = report_workspace(client, db)

    assert rare_word_search(db, report, "the project", 10) == []


def test_rare_word_search_ranks_chunks_with_more_rare_words_first(client, db):
    workspace_id = workspace_for(client, "ada@example.com")
    content = make_pdf(
        "The frontend is hosted on Vercel.",
        "Vercel and Render host the frontend and backend.",
        *[f"Chapter {n} has nothing on this." for n in range(1, 7)],
    )
    upload(client, workspace_id, "report.pdf", content)
    report = db.get(Workspace, uuid.UUID(workspace_id))

    results = rare_word_search(db, report, "Vercel Render", 10)

    assert [result["page_number"] for result in results] == [2, 1]


def test_rare_word_search_only_looks_in_that_workspace(client, db):
    bob_workspace = workspace_for(client, "bob@example.com")
    upload(client, bob_workspace, "bob.pdf", make_pdf("Bob's guide is secret."))
    ada_id = workspace_for(client, "ada@example.com")  # now signed in as Ada
    upload(client, ada_id, "ada.pdf", make_pdf("Ada has no such page."))
    ada = db.get(Workspace, uuid.UUID(ada_id))

    assert rare_word_search(db, ada, "guide", 10) == []


def test_equal_scores_come_back_in_the_same_order_every_time(client):
    # Same words on every page: the same keyword score. Without a tie-breaker
    # PostgreSQL may return equal scores in any order.
    workspace_id = workspace_for(client, "ada@example.com")
    upload(client, workspace_id, "b.pdf", make_pdf("The deposit is paid.", "The deposit is paid."))
    upload(client, workspace_id, "a.pdf", make_pdf("The deposit is paid."))

    results = keyword(client, workspace_id, "deposit").json()

    # By file name, then reading order.
    assert [(r["filename"], r["page_number"]) for r in results] == [
        ("a.pdf", 1),
        ("b.pdf", 1),
        ("b.pdf", 2),
    ]


def routers_workspace(client, db):
    workspace_id = workspace_for(client, "ada@example.com")
    content = make_pdf(
        "The AX-300 admin address is 192.168.8.1.",
        "The AX-500 admin address is 192.168.10.1.",
        "Version 1 of 8 manuals, 192 pages, 168 figures.",
        *[f"Chapter {n} is about something else." for n in range(1, 6)],
    )
    upload(client, workspace_id, "routers.pdf", content)
    return db.get(Workspace, uuid.UUID(workspace_id))


def test_rare_word_search_keeps_an_address_whole(client, db):
    routers = routers_workspace(client, db)

    # Split into "192", "168", "8", "1", it would find page 3 instead.
    results = rare_word_search(db, routers, "What is 192.168.8.1?", 10)

    assert [result["page_number"] for result in results] == [1]


def test_rare_word_search_matches_a_model_code_as_the_documents_store_it(client, db):
    routers = routers_workspace(client, db)

    results = rare_word_search(db, routers, "AX-300", 10)

    # Both pages say "AX", but only page 1 says "-300".
    assert [result["page_number"] for result in results][0] == 1


def test_rare_word_search_handles_a_web_address(client, db):
    workspace_id = workspace_for(client, "ada@example.com")
    content = make_pdf(
        "Open http://router.local:8080/setup to start.",
        *[f"Chapter {n} is about something else." for n in range(1, 6)],
    )
    upload(client, workspace_id, "manual.pdf", content)
    manual = db.get(Workspace, uuid.UUID(workspace_id))

    # PostgreSQL stores "router.local:8080", whose ":" would be a syntax error
    # in a search query if the word weren't quoted.
    results = rare_word_search(db, manual, "What is at http://router.local:8080/setup?", 10)

    assert [result["page_number"] for result in results] == [1]


# Choosing documents: search only in some of a workspace's documents.


def two_leases(client):
    """A workspace with two leases that both talk about rent; returns the
    workspace id and the two document ids."""
    workspace_id = workspace_for(client, "ada@example.com")
    flat = upload(client, workspace_id, "flat.pdf", make_pdf("The flat rent is 900 a month.")).json()["id"]
    shop = upload(client, workspace_id, "shop.pdf", make_pdf("The shop rent is 2000 a month.")).json()["id"]
    return workspace_id, flat, shop


@pytest.mark.parametrize("mode", ["semantic", "keyword"])
def test_search_in_chosen_documents_only(client, mode):
    workspace_id, flat, shop = two_leases(client)

    results = search(client, workspace_id, "rent", mode=mode, document_id=[shop]).json()

    assert [result["filename"] for result in results] == ["shop.pdf"]


def test_search_in_several_chosen_documents(client):
    workspace_id, flat, shop = two_leases(client)

    results = search(client, workspace_id, "rent", document_id=[flat, shop]).json()

    assert sorted(result["filename"] for result in results) == ["flat.pdf", "shop.pdf"]


def test_choosing_a_document_from_another_workspace_is_404(client):
    bob_workspace = workspace_for(client, "bob@example.com")
    bob_doc = upload(client, bob_workspace, "bob.pdf", make_pdf("Bob's rent is secret.")).json()["id"]
    ada_workspace, flat, shop = two_leases(client)  # now signed in as Ada

    response = search(client, ada_workspace, "rent", document_id=[flat, bob_doc])

    # Same answer as for a document that doesn't exist: nothing is revealed.
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"
    assert search(client, ada_workspace, "rent", document_id=[str(uuid.uuid4())]).status_code == 404


def test_rare_word_search_in_chosen_documents(client, db):
    report = report_workspace(client, db)
    other = upload(
        client, str(report.id), "notes.pdf", make_pdf("The guide booked the room.")
    ).json()["id"]

    results = rare_word_search(db, report, "who is the guide", 10, [uuid.UUID(other)])

    assert [result["filename"] for result in results] == ["notes.pdf"]


def test_a_word_common_in_the_chosen_documents_is_not_rare_there(client, db):
    workspace_id = workspace_for(client, "ada@example.com")
    pages = [f"Page {n}: the deposit is held by the landlord." for n in range(1, 5)]
    lease = upload(client, workspace_id, "lease.pdf", make_pdf(*pages)).json()["id"]
    upload(client, workspace_id, "manual.pdf", make_pdf(*[f"Router step {n}." for n in range(1, 13)]))
    ada = db.get(Workspace, uuid.UUID(workspace_id))

    # In the whole workspace "deposit" is in 4 of 16 chunks: rare enough.
    assert rare_word_search(db, ada, "deposit", 10) != []
    # In the lease alone it is on every page, so it picks out nothing.
    assert rare_word_search(db, ada, "deposit", 10, [uuid.UUID(lease)]) == []


def test_at_most_100_documents_can_be_chosen(client):
    workspace_id, flat, shop = two_leases(client)

    response = search(client, workspace_id, "rent", document_id=[str(uuid.uuid4()) for _ in range(101)])

    assert response.status_code == 422
