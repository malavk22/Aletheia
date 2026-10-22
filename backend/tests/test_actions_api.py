from datetime import date

from pdfs import make_pdf
from sqlalchemy import select
from test_actions import GARDEN, NOTICE, contract, found
from test_documents import document_url, upload, workspace_for
from test_facts import fake_gemini_json  # noqa: F401 (a fixture, used by name)

from app.models.document import DocumentAction
from app.models.user import User
from app.qa import llm

# Three actions as Gemini would give them for the test contract: an exact
# deadline, a relative one, and a task without a time.
THREE = {
    "actions": [
        found(),
        found(
            title="Give notice",
            due_text="within 30 days of 1 January 2026",
            due_date="",
            quote=NOTICE,
        ),
        found(
            kind="task",
            title="Keep the garden tidy",
            due_text="",
            due_date="",
            quote=GARDEN,
            part=2,
        ),
    ]
}


def actions_url(document):
    return f"{document_url(document.workspace_id, document.id)}/actions"


def action_url(document, action_id):
    return f"/api/v1/workspaces/{document.workspace_id}/actions/{action_id}"


def extracted(client, db, fake_gemini_json):
    """The test contract with its three actions found, by title."""
    document = contract(client, db)
    fake_gemini_json(THREE)
    body = client.post(actions_url(document)).json()
    return document, {action["title"]: action for action in body["actions"]}


def test_finding_actions_returns_them_with_their_pages(client, db, fake_gemini_json):
    document = contract(client, db)
    fake_gemini_json(THREE)

    response = client.post(actions_url(document))

    assert response.status_code == 200
    body = response.json()
    assert body["extracted_at"] is not None and body["dropped"] == 0
    # Dated first, then the rest in reading order.
    assert [action["title"] for action in body["actions"]] == [
        "Pay 2,000 dollars",
        "Give notice",
        "Keep the garden tidy",
    ]
    payment = body["actions"][0]
    assert (payment["due_kind"], payment["due_date"], payment["due_date_source"]) == (
        "exact",
        "2026-03-15",
        "document",
    )
    assert (payment["filename"], payment["page_number"], payment["status"]) == (
        "contract.pdf",
        1,
        "suggested",
    )
    assert body["actions"][1]["due_date"] is None  # relative: no date


def test_reading_actions_never_calls_gemini(client, db, fake_gemini_json):
    document = contract(client, db)
    calls = fake_gemini_json()

    body = client.get(actions_url(document)).json()

    assert body == {"extracted_at": None, "actions": [], "dropped": None}
    assert calls == []


def test_actions_are_found_only_in_a_processed_document(client, db, fake_gemini_json):
    workspace_id = workspace_for(client, "ada@example.com")
    # A PDF with no text fails processing.
    document_id = upload(client, workspace_id, "scan.pdf", make_pdf("")).json()["id"]
    calls = fake_gemini_json()

    response = client.post(f"{document_url(workspace_id, document_id)}/actions")

    assert response.status_code == 409
    assert response.json()["detail"] == "Actions can be found once the document is processed"
    assert calls == []


def test_when_gemini_fails_the_answer_is_503(client, db, fake_gemini_json):
    document = contract(client, db)
    fake_gemini_json(llm.LLMError("Gemini could not answer: 503 model-x"))

    response = client.post(actions_url(document))

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail == "Couldn't find actions right now. Try again in a minute."
    assert "model-x" not in detail


def test_confirming_records_when_and_who_and_undoing_clears_it(client, db, fake_gemini_json):
    document, actions = extracted(client, db, fake_gemini_json)
    payment = actions["Pay 2,000 dollars"]

    confirmed = client.patch(action_url(document, payment["id"]), json={"status": "confirmed"})

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["confirmed_at"] is not None
    stored = db.get(DocumentAction, confirmed.json()["id"])
    assert stored.confirmed_by == db.scalars(select(User)).one().id

    undone = client.patch(action_url(document, payment["id"]), json={"status": "suggested"})

    assert (undone.json()["status"], undone.json()["confirmed_at"]) == ("suggested", None)
    db.refresh(stored)
    assert stored.confirmed_by is None


def test_a_person_can_date_a_relative_deadline(client, db, fake_gemini_json):
    document, actions = extracted(client, db, fake_gemini_json)
    notice = actions["Give notice"]

    body = client.patch(
        action_url(document, notice["id"]), json={"due_date": "2026-01-31", "status": "confirmed"}
    ).json()

    assert (body["due_date"], body["due_date_source"]) == ("2026-01-31", "person")
    # What the document says is never changed.
    assert (body["due_kind"], body["due_text"]) == ("relative", "within 30 days of 1 January 2026")

    cleared = client.patch(action_url(document, notice["id"]), json={"due_date": None}).json()

    assert (cleared["due_date"], cleared["due_date_source"]) == (None, None)


def test_an_exact_deadline_can_be_changed_by_a_person_but_not_left_without_a_date(
    client, db, fake_gemini_json
):
    document, actions = extracted(client, db, fake_gemini_json)
    payment = actions["Pay 2,000 dollars"]

    cleared = client.patch(action_url(document, payment["id"]), json={"due_date": None})

    assert cleared.status_code == 422
    assert cleared.json()["detail"] == "An exact deadline keeps a date; change it instead"

    changed = client.patch(action_url(document, payment["id"]), json={"due_date": "2026-03-20"})

    # The person's date is marked as theirs, not the document's.
    assert (changed.json()["due_date"], changed.json()["due_date_source"]) == (
        "2026-03-20",
        "person",
    )


def test_only_the_fields_sent_are_changed(client, db, fake_gemini_json):
    document, actions = extracted(client, db, fake_gemini_json)
    payment = actions["Pay 2,000 dollars"]

    body = client.patch(action_url(document, payment["id"]), json={"title": "  Pay the rent  "}).json()

    assert body["title"] == "Pay the rent"
    assert (body["due_date"], body["due_date_source"], body["status"]) == (
        "2026-03-15",
        "document",
        "suggested",
    )


def test_a_bad_change_is_refused(client, db, fake_gemini_json):
    document, actions = extracted(client, db, fake_gemini_json)
    url = action_url(document, actions["Keep the garden tidy"]["id"])

    assert client.patch(url, json={"title": "   "}).json()["detail"] == "The title can't be empty"
    assert client.patch(url, json={"title": "x" * 301}).status_code == 422
    assert client.patch(url, json={"status": "done"}).status_code == 422
    assert client.patch(url, json={"due_date": "15 March"}).status_code == 422


def test_the_workspace_list_can_show_only_confirmed_actions(client, db, fake_gemini_json):
    document, actions = extracted(client, db, fake_gemini_json)
    for title in ("Give notice", "Pay 2,000 dollars"):
        client.patch(action_url(document, actions[title]["id"]), json={"status": "confirmed"})
    url = f"/api/v1/workspaces/{document.workspace_id}/actions"

    confirmed = client.get(url, params={"status": "confirmed"}).json()

    # Dated first: the relative deadline has no date, so it comes last.
    assert [action["title"] for action in confirmed] == ["Pay 2,000 dollars", "Give notice"]
    assert len(client.get(url).json()) == 3
    assert client.get(url, params={"status": "done"}).status_code == 422


def test_other_users_and_other_workspaces_cant_reach_actions(client, db, fake_gemini_json):
    document, actions = extracted(client, db, fake_gemini_json)
    action_id = actions["Pay 2,000 dollars"]["id"]
    # Ada's second workspace: the action isn't in it.
    other = client.post("/api/v1/workspaces", json={"name": "Other"}).json()["id"]
    # The same list of calls as the setup's extraction: count from here.
    calls = fake_gemini_json()
    calls_before = len(calls)

    assert client.patch(
        f"/api/v1/workspaces/{other}/actions/{action_id}", json={"status": "confirmed"}
    ).status_code == 404

    workspace_for(client, "bob@example.com")  # now signed in as Bob
    assert client.get(actions_url(document)).status_code == 404
    assert client.post(actions_url(document)).status_code == 404
    assert client.patch(action_url(document, action_id), json={"status": "confirmed"}).status_code == 404
    assert client.get(f"/api/v1/workspaces/{document.workspace_id}/actions").status_code == 404

    client.post("/api/v1/auth/logout")
    assert client.get(actions_url(document)).status_code == 401
    assert len(calls) == calls_before
    assert db.get(DocumentAction, action_id).status == "suggested"


def test_the_document_list_says_whether_actions_were_found(client, db, fake_gemini_json):
    # The page uses this to find actions on the first click only.
    document = contract(client, db)
    list_url = f"/api/v1/workspaces/{document.workspace_id}/documents"
    fake_gemini_json({"actions": []})

    assert client.get(list_url).json()[0]["actions_extracted_at"] is None
    client.post(actions_url(document))
    assert client.get(list_url).json()[0]["actions_extracted_at"] is not None
