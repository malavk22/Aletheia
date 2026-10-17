import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentPart

# Two sentences this similar (0 to 1, by words) are one sentence that was
# edited; less similar, one was removed and another added.
SAME_SENTENCE = 0.5

# How many new sentences ahead an edited sentence is looked for. Edits stay
# near where the text was; looking everywhere made two unrelated 500-sentence
# documents take 128 s.
LOOKAHEAD = 20

# A sentence ends at . ! or ? followed by a space.
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def compare_versions(db: Session, old: Document, new: Document) -> dict:
    """What changed from `old` to `new`, sentence by sentence, each change with
    its place in both versions. Never calls the AI.

    Kinds of change:
    - "changed": the wording changed (e.g. "2,000" became "2,200").
    - "formatting": only spacing, capitals or punctuation changed.
    - "removed" / "added": a sentence only in the old / new version."""
    old_sentences = _sentences(db, old)
    new_sentences = _sentences(db, new)
    keys_old = [_key(sentence["text"]) for sentence in old_sentences]
    keys_new = [_key(sentence["text"]) for sentence in new_sentences]

    changes = []
    # autojunk=False: by default difflib ignores items that repeat a lot in
    # long sequences, which would hide changes in long documents.
    matcher = SequenceMatcher(None, keys_old, keys_new, autojunk=False)
    for op, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        olds = old_sentences[old_start:old_end]
        news = new_sentences[new_start:new_end]
        if op == "equal":
            # Same words; the text itself may still differ in formatting.
            for before, after in zip(olds, news):
                if before["text"] != after["text"]:
                    changes.append(_change("formatting", before, after))
        else:
            changes.extend(_paired(olds, news))

    counts = {kind: 0 for kind in ("changed", "formatting", "removed", "added")}
    for change in changes:
        counts[change["kind"]] += 1
    return {"changes": changes, "counts": counts}


def _sentences(db: Session, document: Document) -> list[dict]:
    """The document's sentences in reading order, each with its part."""
    parts = db.scalars(
        select(DocumentPart)
        .where(DocumentPart.document_id == document.id)
        .order_by(DocumentPart.position)
    ).all()
    sentences = []
    for part in parts:
        for text in SENTENCE_END.split(" ".join(part.text.split())):
            # Lines without letters are page numbers or separators: when a
            # page is added, every later page number would look "changed".
            if not any(character.isalpha() for character in text):
                continue
            sentences.append(
                {
                    "text": text,
                    "part_position": part.position,
                    "page_number": part.page_number,
                    "heading": part.heading,
                }
            )
    return sentences


def _key(text: str) -> str:
    """The sentence's words only: no capitals, punctuation or extra spaces.
    Two sentences with the same key differ only in formatting. Digits stay,
    so "2,000" and "2,200" have different keys."""
    return " ".join(re.sub(r"[^\w\s]", "", text).casefold().split())


def _paired(olds: list[dict], news: list[dict]) -> list[dict]:
    """A block of old sentences replaced by a block of new ones. Each old
    sentence is paired, in order, with the most similar of the next
    LOOKAHEAD new sentences after the last pair, if similar enough
    ("changed"); the rest are "removed" or "added", in reading order."""
    new_words = [_key(after["text"]).split() for after in news]
    changes = []
    next_new = 0
    for before in olds:
        matcher = SequenceMatcher(None, _key(before["text"]).split(), autojunk=False)
        best, best_score = None, 0.0
        for index in range(next_new, min(next_new + LOOKAHEAD, len(news))):
            matcher.set_seq2(new_words[index])
            score = matcher.ratio()
            # ">" keeps the earliest of equally similar sentences.
            if score > best_score:
                best, best_score = index, score
        if best is None or best_score < SAME_SENTENCE:
            changes.append(_change("removed", before, None))
            continue
        # New sentences skipped over to reach the pair were added.
        changes.extend(_change("added", None, after) for after in news[next_new:best])
        changes.append(_change("changed", before, news[best]))
        next_new = best + 1
    changes.extend(_change("added", None, after) for after in news[next_new:])
    return changes


def _change(kind: str, old: dict | None, new: dict | None) -> dict:
    return {"kind": kind, "old": old, "new": new}
