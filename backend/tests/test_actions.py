import uuid
from datetime import date, datetime, timezone

import pytest
from pdfs import make_pdf
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from test_documents import document_url, upload, workspace_for
from test_facts import fake_gemini_json, item, lease  # noqa: F401 (fake_gemini_json is a fixture)

from app.models.document import Document, DocumentAction, DocumentFact, DocumentPart
from app.models.user import User
from app.qa import llm
from app.services.actions import INSTRUCTIONS, _stated, extract_actions


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
        {"status": "finished"},
        # Confirmed without a time, and a time without being confirmed.
        {"status": "confirmed"},
        {"confirmed_at": datetime(2026, 1, 1, tzinfo=timezone.utc)},
        # Done without having been confirmed, done without a time, and a
        # done time on an action that isn't done.
        {"status": "done", "done_at": datetime(2026, 1, 2, tzinfo=timezone.utc)},
        {"status": "done", "confirmed_at": datetime(2026, 1, 1, tzinfo=timezone.utc)},
        {
            "status": "confirmed",
            "confirmed_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "done_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
        },
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


def test_a_done_action_keeps_when_it_was_confirmed_and_finished(client, db):
    _, document_id = lease(client)
    user = db.scalars(select(User)).one()

    stored = saved(
        db,
        action(
            document_id,
            status="done",
            confirmed_at=datetime(2026, 10, 22, tzinfo=timezone.utc),
            confirmed_by=user.id,
            done_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
            done_by=user.id,
        ),
    )

    assert (stored.status, stored.done_by) == ("done", user.id)


def test_extracting_key_facts_leaves_actions_alone(client, db, fake_gemini_json):
    # Facts and actions are separate: replacing a document's facts must not
    # touch its actions.
    workspace_id, document_id = lease(client)
    saved(db, action(document_id))
    fake_gemini_json({"facts": [item()]})

    client.post(f"{document_url(workspace_id, document_id)}/facts")

    assert len(db.scalars(select(DocumentFact)).all()) == 1
    assert len(db.scalars(select(DocumentAction)).all()) == 1


# extract_actions, with a fake Gemini: these tests check what is kept and how
# dates and confidence are decided, never the real model.

CONTRACT = (
    "Payment of 2,000 dollars is due on 15 March 2026. "
    "The tenant must give notice within 30 days of 1 January 2026. "
    "The report is due by 03/04/2026. The inspection is on 15/03/2026.",
    "The tenant must keep the garden tidy. The deposit must be paid by 15 March.",
)
PAYMENT = "Payment of 2,000 dollars is due on 15 March 2026."
NOTICE = "The tenant must give notice within 30 days of 1 January 2026."
GARDEN = "The tenant must keep the garden tidy."
DEPOSIT = "The deposit must be paid by 15 March."


def contract(client, db):
    workspace_id = workspace_for(client, "ada@example.com")
    document_id = upload(client, workspace_id, "contract.pdf", make_pdf(*CONTRACT)).json()["id"]
    return db.get(Document, uuid.UUID(document_id))


def found(**fields):
    """An action as Gemini would give it: the payment deadline, unless told otherwise."""
    return {
        "kind": "deadline",
        "title": "Pay 2,000 dollars",
        "responsible": "the tenant",
        "due_text": "on 15 March 2026",
        "due_date": "2026-03-15",
        "quote": PAYMENT,
        "part": 1,
        **fields,
    }


def stored_actions(db, document):
    return db.scalars(
        select(DocumentAction)
        .where(DocumentAction.document_id == document.id)
        .order_by(DocumentAction.title)
    ).all()


def only(db, document):
    [stored] = stored_actions(db, document)
    return stored


def test_a_full_date_written_in_the_document_makes_an_exact_deadline(
    client, db, fake_gemini_json
):
    document = contract(client, db)
    fake_gemini_json({"actions": [found()]})

    result = extract_actions(db, document)

    stored = only(db, document)
    assert result == {"kept": 1, "dropped": 0}
    assert (stored.due_kind, stored.due_date, stored.due_date_source) == (
        "exact",
        date(2026, 3, 15),
        "document",
    )
    assert (stored.due_text, stored.confidence, stored.status) == (
        "on 15 March 2026",
        "high",
        "suggested",
    )
    assert (stored.quote, stored.part_position, stored.responsible) == (PAYMENT, 1, "the tenant")
    assert document.actions_extracted_at is not None


@pytest.mark.parametrize(
    "due_date",
    [
        # Worked out from the period: not written in the document.
        "2026-01-31",
        # The date that is written is the start of the period, not the deadline.
        "2026-01-01",
    ],
)
def test_a_period_never_gets_a_date(client, db, fake_gemini_json, due_date):
    document = contract(client, db)
    fake_gemini_json(
        {
            "actions": [
                found(
                    title="Give notice",
                    due_text="within 30 days of 1 January 2026",
                    due_date=due_date,
                    quote=NOTICE,
                )
            ]
        }
    )

    extract_actions(db, document)

    stored = only(db, document)
    assert (stored.due_kind, stored.due_date, stored.due_date_source) == ("relative", None, None)
    assert stored.due_text == "within 30 days of 1 January 2026"
    # Gemini gave a date the document doesn't support: a warning sign.
    assert stored.confidence == "low"


def test_a_missing_year_is_never_guessed(client, db, fake_gemini_json):
    document = contract(client, db)
    fake_gemini_json(
        {
            "actions": [
                found(
                    title="Pay the deposit",
                    due_text="by 15 March",
                    due_date="2026-03-15",
                    quote=DEPOSIT,
                    part=2,
                )
            ]
        }
    )

    extract_actions(db, document)

    stored = only(db, document)
    assert (stored.due_kind, stored.due_date, stored.confidence) == ("relative", None, "low")


@pytest.mark.parametrize(
    "due_text, due_date, quote, exact",
    [
        # 03/04 could be 3 April or 4 March: choosing would be a guess.
        ("by 03/04/2026", "2026-04-03", "The report is due by 03/04/2026.", False),
        # 15 can't be a month, so 15/03/2026 is 15 March.
        ("on 15/03/2026", "2026-03-15", "The inspection is on 15/03/2026.", True),
    ],
)
def test_a_numeric_date_is_exact_only_when_it_cant_be_misread(
    client, db, fake_gemini_json, due_text, due_date, quote, exact
):
    document = contract(client, db)
    fake_gemini_json({"actions": [found(due_text=due_text, due_date=due_date, quote=quote)]})

    extract_actions(db, document)

    stored = only(db, document)
    assert (stored.due_kind == "exact", stored.due_date is not None) == (exact, exact)


def test_an_action_without_a_time_has_no_deadline(client, db, fake_gemini_json):
    document = contract(client, db)
    fake_gemini_json(
        {
            "actions": [
                found(
                    kind="task",
                    title="Keep the garden tidy",
                    responsible="",
                    due_text="",
                    due_date="",
                    quote=GARDEN,
                    part=2,
                )
            ]
        }
    )

    extract_actions(db, document)

    stored = only(db, document)
    assert (stored.due_kind, stored.due_text, stored.due_date) == ("none", None, None)
    assert (stored.confidence, stored.responsible) == ("medium", None)


def test_a_relative_deadline_without_a_suggested_date_is_medium(client, db, fake_gemini_json):
    document = contract(client, db)
    fake_gemini_json(
        {
            "actions": [
                found(
                    title="Give notice",
                    due_text="within 30 days of 1 January 2026",
                    due_date="",
                    quote=NOTICE,
                )
            ]
        }
    )

    extract_actions(db, document)

    stored = only(db, document)
    assert (stored.due_kind, stored.confidence) == ("relative", "medium")


def test_text_read_by_ocr_is_low_confidence(client, db, fake_gemini_json):
    document = contract(client, db)
    db.get(DocumentPart, (document.id, 1)).source = "ocr"
    fake_gemini_json({"actions": [found()]})

    extract_actions(db, document)

    # Still exact (the date is written there), but the text may be misread.
    stored = only(db, document)
    assert (stored.due_kind, stored.confidence) == ("exact", "low")


def test_an_action_is_dropped_unless_its_evidence_checks_out(client, db, fake_gemini_json):
    document = contract(client, db)
    fake_gemini_json(
        {
            "actions": [
                # Each wrong one has its own title, so only its own check can
                # stop it (not the duplicate check).
                found(title="Wrong page", part=2),  # the quote is on page 1, not 2
                found(title="Made up", quote="Payment is due on 1 April 2026."),
                found(title="Wrong when", due_text="on 20 March 2026"),  # not in the quote
                found(title="Wrong kind", kind="reminder"),
                found(title=""),
                found(title="Bool part", part=True),  # True is not part 1
                found(title="No part", part=9),
                found(),  # the real one, given twice:
                found(title="pay 2,000 DOLLARS"),  # kept once
            ]
        }
    )

    result = extract_actions(db, document)

    assert result == {"kept": 1, "dropped": 8}
    assert only(db, document).title == "Pay 2,000 dollars"


def test_extracting_again_keeps_what_a_person_decided(client, db, fake_gemini_json):
    document = contract(client, db)
    garden = {"kind": "task", "due_text": "", "due_date": "", "quote": GARDEN, "part": 2}
    notice = {"due_text": "within 30 days of 1 January 2026", "due_date": "", "quote": NOTICE}
    fake_gemini_json(
        {
            "actions": [
                found(),
                found(title="Keep the garden tidy", **garden),
                found(title="Give notice", **notice),
            ]
        },
        # The second run finds all three again, worded a little differently.
        {
            "actions": [
                found(title="Make the payment"),
                found(title="Tidy the garden", **garden),
                found(title="Notify the landlord", **notice),
            ]
        },
    )
    extract_actions(db, document)
    by_title = {action.title: action for action in stored_actions(db, document)}
    by_title["Pay 2,000 dollars"].status = "confirmed"
    by_title["Pay 2,000 dollars"].confirmed_at = datetime.now(timezone.utc)
    by_title["Keep the garden tidy"].status = "dismissed"
    db.flush()

    extract_actions(db, document)

    # The confirmed and dismissed actions stay as they were and aren't
    # suggested again; the one suggestion is replaced by the new wording.
    assert [(action.title, action.status) for action in stored_actions(db, document)] == [
        ("Keep the garden tidy", "dismissed"),
        ("Notify the landlord", "suggested"),
        ("Pay 2,000 dollars", "confirmed"),
    ]


def test_extracting_again_keeps_a_done_action(client, db, fake_gemini_json):
    document = contract(client, db)
    fake_gemini_json({"actions": [found()]}, {"actions": [found(title="Make the payment")]})
    extract_actions(db, document)
    [payment] = stored_actions(db, document)
    payment.status = "done"
    payment.confirmed_at = payment.done_at = datetime.now(timezone.utc)
    db.flush()

    extract_actions(db, document)

    # Its sentence isn't suggested again.
    assert [(a.title, a.status) for a in stored_actions(db, document)] == [
        ("Pay 2,000 dollars", "done")
    ]


def test_when_gemini_fails_nothing_changes(client, db, fake_gemini_json):
    document = contract(client, db)
    fake_gemini_json({"actions": [found()]}, llm.LLMError("Gemini could not answer: 503"))
    extract_actions(db, document)
    first_time = document.actions_extracted_at

    with pytest.raises(llm.LLMError):
        extract_actions(db, document)

    assert len(stored_actions(db, document)) == 1
    assert document.actions_extracted_at == first_time


def test_the_prompt_numbers_the_parts_and_forbids_working_out_dates(
    client, db, fake_gemini_json
):
    document = contract(client, db)
    calls = fake_gemini_json({"actions": []})

    extract_actions(db, document)

    assert "[part 1] (p. 1)" in calls[0]["prompt"]
    assert "[part 2] (p. 2)" in calls[0]["prompt"]
    assert "Never work out a date" in calls[0]["instructions"]
    # Extracted, none found: different from never extracted.
    assert document.actions_extracted_at is not None


@pytest.mark.parametrize(
    "text, day, stated",
    [
        ("on 15 March 2026", date(2026, 3, 15), True),
        ("by Mar 15, 2026", date(2026, 3, 15), True),
        ("before 15 Sept 2026", date(2026, 9, 15), True),
        ("on 2026-03-15", date(2026, 3, 15), True),
        ("on 15/03/2026", date(2026, 3, 15), True),
        ("on 03/03/2026", date(2026, 3, 3), True),  # the same either way round
        ("by 03/04/2026", date(2026, 4, 3), False),  # 3 April or 4 March?
        ("by 15 March", date(2026, 3, 15), False),  # no year
        ("on 15 March 2026", date(2026, 3, 16), False),  # another day
        ("on 15 March 2026", date(2026, 4, 15), False),  # another month
        ("on 15 March 2025", date(2026, 3, 15), False),  # another year
    ],
)
def test_a_date_counts_only_if_the_text_writes_it_in_full(text, day, stated):
    assert _stated(day, text) is stated


def test_the_prompt_is_for_any_kind_of_document():
    # Not tied to contracts: it names other kinds of documents, and it says
    # what is NOT an action, such as a feature a system must have, the steps
    # of a plan a report describes, or a role's description.
    for words in (
        "meeting notes", "syllabus", "invoice", "may", "already done", "feature",
        "steps of a plan", "unless it asks the reader", "a role or job",
    ):
        assert words in INSTRUCTIONS
    assert "tenant" not in INSTRUCTIONS
