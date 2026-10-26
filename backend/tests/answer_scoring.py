"""Scores recorded answers (V0.9) with rules: offline, free, and the same
result every run. No AI judges the answers.

For each answer:
- facts: which expected facts the answer states;
- answer pages cited: which labelled pages it cites;
- facts in cited passages: whether each fact it states is also in a passage
  it cites (the citation really backs the fact);
- sentences cited: which sentences carry at least one [n];
- unsupported numbers: numbers in a sentence that aren't in the passages that
  sentence cites (or any number in a sentence with no citation): a figure the
  documents don't give, such as a calculation;
- abstention: a question the documents don't answer gets NOT_FOUND and no
  citations, and one they do answer doesn't.
"""

import re
import statistics

from app.qa.support import MARKER, sentences, unsupported_numbers

MONTHS = (
    "january february march april may june july august september october november december"
).split()
_MONTH = "|".join(MONTHS)
# "20 March", "20 March 2026", "March 20", "March 20, 2026".
_DAY_MONTH = re.compile(rf"\b(\d{{1,2}}) ({_MONTH})(?:,? (\d{{4}}))?\b")
_MONTH_DAY = re.compile(rf"\b({_MONTH}) (\d{{1,2}})(?:,? (\d{{4}}))?\b")

def normalize(text: str) -> str:
    """Lower case, single spaces, straight quotes, and every date written
    one way: "March 20, 2026" and "20 March 2026" both become
    "20 march 2026". Only the order changes: the day, month and year stay
    as written, so a different date stays different."""
    text = text.lower().replace("’", "'").replace("‘", "'")
    text = re.sub(r"\s+", " ", text)
    text = _MONTH_DAY.sub(lambda m: " ".join(filter(None, (m[2], m[1], m[3]))), text)
    return _DAY_MONTH.sub(lambda m: " ".join(filter(None, (m[1], m[2], m[3]))), text)


def contains(text: str, phrase: str) -> bool:
    """`phrase` in `text`, as whole words and whole numbers: "24" is not in
    "2024", "500" not in "1,500", "18" not in "18,400", "2 march" not in
    "12 march"."""
    pattern = r"(?<![\w.,])" + re.escape(normalize(phrase)) + r"(?!\w|[.,]\d)"
    return re.search(pattern, normalize(text)) is not None


def states(text: str, fact: tuple[str, ...]) -> bool:
    """The text states the fact in one of its ways of writing it."""
    return any(contains(text, way) for way in fact)


def score_answer(record: dict, facts: list, pages: list, not_found: str) -> dict:
    """The checks above for one answer to a question the documents answer."""
    answer = record["answer"]
    passages = {c["number"]: c["text"] for c in record["citations"]}
    cited_pages = {(c["filename"], c["page_number"]) for c in record["citations"]}
    stated = [fact for fact in facts if states(answer, fact)]
    parts = sentences(answer)
    unsupported = {s: unsupported_numbers(s, passages) for s in parts}
    return {
        "facts": len(stated) / len(facts),
        "correct": len(stated) == len(facts),
        "answer pages cited": sum(page in cited_pages for page in map(tuple, pages)) / len(pages),
        "facts in cited passages": (
            sum(any(states(text, fact) for text in passages.values()) for fact in stated) / len(stated)
            if stated
            else 0.0
        ),
        "sentences cited": sum(bool(MARKER.search(s)) for s in parts) / len(parts),
        "uncited sentences": [s for s in parts if not MARKER.search(s)],
        "unsupported numbers": {s: sorted(n) for s, n in unsupported.items() if n},
        "abstained": answer.strip() == not_found,
        "seconds": record["seconds"],
    }


def scorecard(recorded: dict, answerable: list, unanswerable: list, not_found: str) -> dict:
    """Every recorded answer scored, and the totals."""
    rows = {
        question: score_answer(recorded[question], facts, pages, not_found)
        for question, _kind, pages, facts in answerable
    }
    abstentions = [
        recorded[q]["answer"].strip() == not_found and not recorded[q]["citations"] for q in unanswerable
    ]
    seconds = [recorded[q]["seconds"] for q in recorded]
    totals = {
        "facts": statistics.mean(r["facts"] for r in rows.values()),
        "correct": statistics.mean(r["correct"] for r in rows.values()),
        "answer pages cited": statistics.mean(r["answer pages cited"] for r in rows.values()),
        "facts in cited passages": statistics.mean(r["facts in cited passages"] for r in rows.values()),
        "sentences cited": statistics.mean(r["sentences cited"] for r in rows.values()),
        "answers with an uncited sentence": statistics.mean(bool(r["uncited sentences"]) for r in rows.values()),
        "answers with an unsupported number": statistics.mean(
            bool(r["unsupported numbers"]) for r in rows.values()
        ),
        "wrongly abstained": statistics.mean(r["abstained"] for r in rows.values()),
        "abstained when unanswerable": statistics.mean(abstentions),
        "median seconds": statistics.median(seconds),
        "max seconds": max(seconds),
    }
    return {"rows": rows, "totals": {name: round(value, 3) for name, value in totals.items()}}
