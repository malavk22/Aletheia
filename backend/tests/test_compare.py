import uuid

from pdfs import make_pdf
from test_documents import upload, workspace_for

from app.models.document import Document
from app.services.compare import compare_versions

# Two versions of a made-up lease. Version 2: the rent changed, a sentence on
# page 1 was only re-typed, the pets rule was removed, and a new page about
# parking was put in before the old page 2.
LEASE_V1 = (
    "Rent is 2,000 dollars a month. The tenant pays for water.\n1",
    "Pets are not allowed. The lease ends on 31 December 2026.\n2",
)
LEASE_V2 = (
    "Rent is 2,200 dollars a month. The tenant pays for WATER!\n1",
    "Parking costs 50 dollars a month.\n2",
    "The lease ends on 31 December 2026.\n3",
)


def documents(client, db, old_pages, new_pages):
    workspace_id = workspace_for(client, "ada@example.com")
    ids = [
        upload(client, workspace_id, name, make_pdf(*pages)).json()["id"]
        for name, pages in (("lease-v1.pdf", old_pages), ("lease-v2.pdf", new_pages))
    ]
    return [db.get(Document, uuid.UUID(document_id)) for document_id in ids]


def place(side):
    return (side["page_number"], side["text"]) if side else None


def test_identical_documents_have_no_changes(client, db):
    old, new = documents(client, db, LEASE_V1, LEASE_V1)

    result = compare_versions(db, old, new)

    assert result["changes"] == []
    assert result["counts"] == {"changed": 0, "formatting": 0, "removed": 0, "added": 0}


def test_each_change_has_its_kind_and_its_page_in_both_versions(client, db):
    old, new = documents(client, db, LEASE_V1, LEASE_V2)

    result = compare_versions(db, old, new)

    assert [(c["kind"], place(c["old"]), place(c["new"])) for c in result["changes"]] == [
        (
            "changed",
            (1, "Rent is 2,000 dollars a month."),
            (1, "Rent is 2,200 dollars a month."),
        ),
        (
            "formatting",
            (1, "The tenant pays for water."),
            (1, "The tenant pays for WATER!"),
        ),
        ("removed", (2, "Pets are not allowed."), None),
        ("added", None, (2, "Parking costs 50 dollars a month.")),
    ]
    assert result["counts"] == {"changed": 1, "formatting": 1, "removed": 1, "added": 1}


def test_a_sentence_that_only_moved_to_another_page_is_not_a_change(client, db):
    # "The lease ends…" is on p. 2 in version 1 and p. 3 in version 2.
    old, new = documents(client, db, LEASE_V1, LEASE_V2)

    texts = [
        side["text"]
        for change in compare_versions(db, old, new)["changes"]
        for side in (change["old"], change["new"])
        if side
    ]

    assert "The lease ends on 31 December 2026." not in texts


def test_page_numbers_are_not_reported_as_changes(client, db):
    # Version 2's pages end in 1, 2, 3; version 1's in 1, 2. Lines without
    # letters are skipped, so no "added: 3".
    old, new = documents(client, db, LEASE_V1, LEASE_V2)

    for change in compare_versions(db, old, new)["changes"]:
        for side in (change["old"], change["new"]):
            assert side is None or any(character.isalpha() for character in side["text"])


def test_an_unrelated_sentence_is_removed_and_added_not_changed(client, db):
    # They share "the" twice, about a third of their words: below SAME_SENTENCE.
    old, new = documents(
        client,
        db,
        ("The tenant must keep the garden tidy.",),
        ("The landlord repairs the roof.",),
    )

    kinds = [change["kind"] for change in compare_versions(db, old, new)["changes"]]

    assert kinds == ["removed", "added"]


def test_the_earliest_of_equally_similar_sentences_is_paired(client, db):
    # Both new sentences are equally close to the old one: the first is the
    # edit, the second was added.
    old, new = documents(
        client,
        db,
        ("Rent is 2,000 dollars a month.",),
        ("Rent is 2,100 dollars a month. Rent is 2,100 dollars a month.",),
    )

    result = compare_versions(db, old, new)

    assert [change["kind"] for change in result["changes"]] == ["changed", "added"]


def test_an_edit_is_looked_for_only_lookahead_sentences_ahead(client, db):
    # 25 new sentences come before the edited one, more than LOOKAHEAD (20):
    # the edit is shown as removed + added (the known limit of the window).
    added = " ".join(f"Clause {number} was added in this version." for number in range(25))
    old, new = documents(
        client,
        db,
        ("Rent is 2,000 dollars a month.",),
        (f"{added} Rent is 2,200 dollars a month.",),
    )

    counts = compare_versions(db, old, new)["counts"]

    assert (counts["changed"], counts["removed"], counts["added"]) == (0, 1, 26)


def test_comparing_the_other_way_swaps_removed_and_added(client, db):
    old, new = documents(client, db, LEASE_V1, LEASE_V2)

    counts = compare_versions(db, new, old)["counts"]

    assert counts == {"changed": 1, "formatting": 1, "removed": 1, "added": 1}
