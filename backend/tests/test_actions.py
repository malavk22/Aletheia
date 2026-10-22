from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from test_documents import document_url
from test_facts import fake_gemini_json, item, lease  # noqa: F401 (fake_gemini_json is a fixture)

from app.models.document import DocumentAction, DocumentFact
from app.models.user import User


def action(document_id, **fields):
    """A suggested task with no deadline, on part 1, unless told otherwise."""
    return DocumentAction(
        document_id=document_id,
        part_position=fields.pop("part_position", 1),
        kind=fields.pop("kind", "task"),
        title=fields.pop("title", "Pay the rent"),
        due_kind=fields.pop("due_kind", "none"),
        quote=fields.pop("quote", "Rent is 2,000 dollars a month."),
        confidence=fields.pop("confidence", "medium"),
        **fields,
    )


def saved(db, new_action):
    db.add(new_action)
    db.flush()
    return new_action


def refused(db, new_action):
    """True if the database refuses to store the action."""
    with db.begin_nested():
        db.add(new_action)
        try:
            db.flush()
        except IntegrityError:
            return True
    return False


def test_an_action_starts_as_a_suggestion_with_its_quote_and_part(client, db):
    _, document_id = lease(client)

    stored = saved(db, action(document_id))

    db.refresh(stored)
    assert stored.status == "suggested"
    assert (stored.quote, stored.part_position) == ("Rent is 2,000 dollars a month.", 1)
    assert stored.confirmed_at is None and stored.created_at is not None


def test_an_action_must_point_to_a_real_part(client, db):
    _, document_id = lease(client)

    # The lease has 2 pages; there is no part 9.
    assert refused(db, action(document_id, part_position=9))


def test_deleting_the_document_deletes_its_actions(client, db):
    workspace_id, document_id = lease(client)
    saved(db, action(document_id))

    assert client.delete(document_url(workspace_id, document_id)).status_code == 204

    assert db.scalars(select(DocumentAction)).all() == []


def test_an_exact_deadline_keeps_its_date_and_its_words(client, db):
    _, document_id = lease(client)

    stored = saved(
        db,
        action(
            document_id,
            kind="deadline",
            part_position=2,
            due_kind="exact",
            due_text="1 January 2026",
            due_date=date(2026, 1, 1),
            due_date_source="document",
            quote="The lease starts on 1 January 2026.",
        ),
    )

    assert (stored.due_date, stored.due_date_source) == (date(2026, 1, 1), "document")


def test_a_relative_deadline_is_stored_without_a_date(client, db):
    _, document_id = lease(client)

    stored = saved(
        db, action(document_id, kind="deadline", due_kind="relative", due_text="within 30 days")
    )

    assert (stored.due_date, stored.due_text) == (None, "within 30 days")


def test_the_document_can_never_give_a_relative_deadline_a_date(client, db):
    # "within 30 days" doesn't say of what: a date from the document would be
    # invented. The database refuses it.
    _, document_id = lease(client)

    assert refused(
        db,
        action(
            document_id,
            due_kind="relative",
            due_text="within 30 days",
            due_date=date(2026, 2, 1),
            due_date_source="document",
        ),
    )


def test_a_person_can_give_a_relative_deadline_a_date(client, db):
    _, document_id = lease(client)

    stored = saved(
        db,
        action(
            document_id,
            due_kind="relative",
            due_text="within 30 days",
            due_date=date(2026, 2, 1),
            due_date_source="person",
        ),
    )

    assert stored.due_date_source == "person"


@pytest.mark.parametrize(
    "fields",
    [
        # An exact deadline without its date.
        {"due_kind": "exact", "due_text": "1 January 2026"},
        # A date that doesn't say where it came from, and the other way round.
        {"due_kind": "exact", "due_text": "1 January 2026", "due_date": date(2026, 1, 1)},
        {"due_date_source": "person"},
        # A deadline without its own words.
        {"due_kind": "relative"},
        # Unknown values.
        {"kind": "reminder"},
        {"due_kind": "soon", "due_text": "soon"},
        {"confidence": "certain"},
        {"status": "done"},
        # Confirmed without a time, and a time without being confirmed.
        {"status": "confirmed"},
        {"confirmed_at": datetime(2026, 1, 1, tzinfo=timezone.utc)},
    ],
)
def test_the_database_refuses_an_action_that_breaks_a_rule(client, db, fields):
    _, document_id = lease(client)

    assert refused(db, action(document_id, **fields))


def test_a_confirmed_action_keeps_when_and_by_whom(client, db):
    _, document_id = lease(client)
    user = db.scalars(select(User)).one()

    stored = saved(
        db,
        action(
            document_id,
            status="confirmed",
            confirmed_at=datetime(2026, 10, 22, tzinfo=timezone.utc),
            confirmed_by=user.id,
        ),
    )

    assert (stored.status, stored.confirmed_by) == ("confirmed", user.id)


def test_extracting_key_facts_leaves_actions_alone(client, db, fake_gemini_json):
    # Facts and actions are separate: replacing a document's facts must not
    # touch its actions.
    workspace_id, document_id = lease(client)
    saved(db, action(document_id))
    fake_gemini_json({"facts": [item()]})

    client.post(f"{document_url(workspace_id, document_id)}/facts")

    assert len(db.scalars(select(DocumentFact)).all()) == 1
    assert len(db.scalars(select(DocumentAction)).all()) == 1
