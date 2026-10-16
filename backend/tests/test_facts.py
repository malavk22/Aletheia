import uuid

import pytest
from pdfs import make_pdf
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from test_documents import document_url, upload, workspace_for

from app.models.document import Document, DocumentFact


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
