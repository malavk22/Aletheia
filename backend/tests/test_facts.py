import uuid

import pytest
from pdfs import make_pdf
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from test_documents import document_url, upload, workspace_for

from app.models.document import Document, DocumentFact
from app.qa import llm
from app.services import facts as facts_service
from app.services.facts import KINDS, extract_facts


def lease(client):
    workspace_id = workspace_for(client, "ada@example.com")
    content = make_pdf("Rent is 2,000 dollars a month.", "The lease starts on 1 January 2026.")
    document_id = upload(client, workspace_id, "lease.pdf", content).json()["id"]
    return workspace_id, uuid.UUID(document_id)


def fact(document_id, position, part_position, **fields):
    return DocumentFact(
        document_id=document_id,
        position=position,
        part_position=part_position,
        kind=fields.get("kind", "date"),
        value=fields.get("value", "1 January 2026"),
        normalized=fields.get("normalized", "2026-01-01"),
        about=fields.get("about", "lease start"),
        quote=fields.get("quote", "The lease starts on 1 January 2026."),
    )


def test_a_fact_is_stored_with_its_quote_and_part(client, db):
    _, document_id = lease(client)

    db.add(fact(document_id, 1, part_position=2))
    db.flush()

    stored = db.scalars(select(DocumentFact)).one()
    assert (stored.kind, stored.normalized, stored.part_position) == ("date", "2026-01-01", 2)
    assert db.get(Document, document_id).facts_extracted_at is None


def test_a_fact_must_point_to_a_real_part(client, db):
    _, document_id = lease(client)

    # The lease has 2 pages; there is no part 9.
    db.add(fact(document_id, 1, part_position=9))
    with pytest.raises(IntegrityError):
        db.flush()


def test_deleting_the_document_deletes_its_facts(client, db):
    workspace_id, document_id = lease(client)
    db.add(fact(document_id, 1, part_position=2))
    db.flush()

    assert client.delete(document_url(workspace_id, document_id)).status_code == 204

    assert db.scalars(select(DocumentFact)).all() == []


# extract_facts, with a fake Gemini: these tests check what is sent and what
# is kept, never the real model.


@pytest.fixture
def fake_gemini_json(monkeypatch):
    """Replaces llm.generate_json with fixed replies, one per call, and
    remembers each prompt."""
    calls = []

    def install(*replies):
        replies = list(replies)

        def generate_json(instructions, prompt, schema):
            calls.append({"instructions": instructions, "prompt": prompt, "schema": schema})
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply

        monkeypatch.setattr(llm, "generate_json", generate_json)
        return calls

    return install


def item(**fields):
    return {
        "kind": "amount",
        "value": "2,000 dollars",
        "about": "monthly rent",
        "normalized": "",
        "quote": "Rent is 2,000 dollars a month.",
        "part": 1,
        **fields,
    }


def stored(db, document_id):
    return db.scalars(
        select(DocumentFact)
        .where(DocumentFact.document_id == document_id)
        .order_by(DocumentFact.position)
    ).all()


def test_facts_are_extracted_checked_and_stored(client, db, fake_gemini_json):
    _, document_id = lease(client)
    calls = fake_gemini_json({"facts": [
        item(),
        item(kind="date", value="1 January 2026", about="lease start",
             normalized="2026-01-01", quote="The lease starts on 1 January 2026.", part=2),
    ]})
    document = db.get(Document, document_id)

    result = extract_facts(db, document)

    assert result == {"kept": 2, "dropped": 0}
    facts = stored(db, document_id)
    assert [(f.position, f.kind, f.value, f.part_position) for f in facts] == [
        (1, "amount", "2,000 dollars", 1),
        (2, "date", "1 January 2026", 2),
    ]
    assert facts[1].normalized == "2026-01-01"
    assert facts[0].normalized is None
    assert facts[0].about == "monthly rent"
    assert document.facts_extracted_at is not None
    # The pages are sent labelled with their part number and page.
    prompt = calls[0]["prompt"]
    assert prompt.startswith("Document: lease.pdf")
    assert "[part 1] (p. 1)\nRent is 2,000 dollars a month." in prompt
    assert "[part 2] (p. 2)" in prompt
    assert calls[0]["schema"]["properties"]["facts"]["items"]["properties"]["kind"]["enum"] == list(KINDS)


@pytest.mark.parametrize(
    "bad",
    [
        {"quote": "Rent is 3,000 dollars a month."},  # not in the document
        {"part": 2},  # in the document, but not on that page
        {"part": 9},  # no such part
        {"part": True},  # not a part number
        {"kind": "colour"},  # not a kind we know
        {"value": "  "},  # empty
        {"quote": ""},  # no evidence
    ],
    ids=["made-up quote", "wrong page", "missing part", "bool part", "unknown kind",
         "empty value", "empty quote"],
)
def test_facts_without_real_evidence_are_dropped(client, db, fake_gemini_json, bad):
    _, document_id = lease(client)
    fake_gemini_json({"facts": [item(), item(**bad)]})

    result = extract_facts(db, db.get(Document, document_id))

    assert result == {"kept": 1, "dropped": 1}
    assert len(stored(db, document_id)) == 1


def test_quotes_match_with_spacing_and_capitals_ignored(client, db, fake_gemini_json):
    _, document_id = lease(client)
    fake_gemini_json({"facts": [item(quote="rent  is 2,000\ndollars A MONTH.")]})

    assert extract_facts(db, db.get(Document, document_id))["kept"] == 1
    # The quote is stored tidied, as one line.
    assert stored(db, document_id)[0].quote == "rent is 2,000 dollars A MONTH."


@pytest.mark.parametrize("normalized", ["2026-02-30", "1 Jan 2026", "2026-1-1", ""])
def test_only_real_iso_dates_are_kept_as_normalized(client, db, fake_gemini_json, normalized):
    _, document_id = lease(client)
    fake_gemini_json({"facts": [item(
        kind="date", value="1 January 2026", normalized=normalized,
        quote="The lease starts on 1 January 2026.", part=2,
    )]})

    extract_facts(db, db.get(Document, document_id))

    # The date fact is kept (its quote is real); only the bad form is dropped.
    assert stored(db, document_id)[0].normalized is None


def test_the_same_fact_twice_is_kept_once(client, db, fake_gemini_json):
    _, document_id = lease(client)
    fake_gemini_json({"facts": [item(), item(value="2,000 DOLLARS")]})

    assert extract_facts(db, db.get(Document, document_id)) == {"kept": 1, "dropped": 1}


def test_extracting_again_replaces_the_old_facts(client, db, fake_gemini_json):
    _, document_id = lease(client)
    document = db.get(Document, document_id)
    fake_gemini_json({"facts": [item(), item(kind="date", value="1 January 2026",
                     quote="The lease starts on 1 January 2026.", part=2)]},
                     {"facts": [item()]})

    extract_facts(db, document)
    extract_facts(db, document)

    assert [f.kind for f in stored(db, document_id)] == ["amount"]


def test_when_gemini_fails_the_old_facts_are_kept(client, db, fake_gemini_json):
    _, document_id = lease(client)
    document = db.get(Document, document_id)
    fake_gemini_json({"facts": [item()]}, llm.LLMError("Gemini could not answer: 503"))
    extract_facts(db, document)
    first_run = document.facts_extracted_at

    with pytest.raises(llm.LLMError):
        extract_facts(db, document)

    assert len(stored(db, document_id)) == 1
    assert document.facts_extracted_at == first_run


def test_nothing_found_is_recorded_as_extracted(client, db, fake_gemini_json):
    _, document_id = lease(client)
    fake_gemini_json({"facts": []})
    document = db.get(Document, document_id)

    assert extract_facts(db, document) == {"kept": 0, "dropped": 0}
    assert document.facts_extracted_at is not None


def test_long_documents_are_sent_in_batches(client, db, fake_gemini_json, monkeypatch):
    workspace_id = workspace_for(client, "ada@example.com")
    pages = [f"Page {n} says the fee is {n} dollars." for n in range(1, 6)]
    document_id = upload(client, workspace_id, "fees.pdf", make_pdf(*pages)).json()["id"]
    # Each page is about 35 characters: at most 2 pages fit in 80.
    monkeypatch.setattr(facts_service, "BATCH_CHARS", 80)
    calls = fake_gemini_json(
        {"facts": [item(value="1 dollars", quote="Page 1 says the fee is 1 dollars.", part=1)]},
        {"facts": [item(value="3 dollars", quote="Page 3 says the fee is 3 dollars.", part=3)]},
        {"facts": []},
    )

    result = extract_facts(db, db.get(Document, uuid.UUID(document_id)))

    assert len(calls) == 3
    assert "[part 1]" in calls[0]["prompt"] and "[part 2]" in calls[0]["prompt"]
    assert "[part 3]" in calls[1]["prompt"] and "[part 2]" not in calls[1]["prompt"]
    assert "[part 5]" in calls[2]["prompt"]
    assert result == {"kept": 2, "dropped": 0}
