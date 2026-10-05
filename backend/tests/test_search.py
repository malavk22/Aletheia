from docxs import make_docx
from pdfs import make_pdf
from test_documents import upload, workspace_for

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
