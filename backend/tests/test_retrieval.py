"""The retrieval check (V0.8): how well Ask finds the passages that answer a
question, scored on the fixed set in retrieval_set.py with the real
embedding model (not the fake one other tests use). No Gemini is called.

Scores, for the PASSAGES passages the model would read:
- recall@6: the share of answer pages among them; the main score, because
  a page the model never reads can't be in the answer.
- recall@3: the same for the first 3 only; stricter, shows ranking.
- hit@1: the first passage is on an answer page.
- MRR: 1 / the rank of the first passage on an answer page (0 if none),
  averaged: 1.0 means always first, 0.5 second, and so on.
- all parts: for two-part questions, both answer pages were found.

Run with -s to see the scorecard: pytest tests/test_retrieval.py -s
"""

import statistics
import textwrap
import time

import pytest
from pdfs import make_pdf
from retrieval_set import DOCUMENTS, OTHER_WORKSPACE, QUESTIONS
from test_documents import upload, workspace_for
from test_qa import workspace

from app.documents import embeddings

# Imported before the fake_embeddings fixture replaces them: the real model.
from app.documents.embeddings import embed_passages, embed_query
from app.services.qa import PASSAGES, _find_passages

# Recorded on 2026-10-23 with the V0.7 retrieval (rare words first, then
# meaning; equal scores in file and reading order), 42 questions over 36
# pages. A change that scores lower fails this test. By kind, recall@6:
# words 0.9, reworded 0.846, names 0.9, parts 0.889; median 48 ms a question.
BASELINE = {"recall@6": 0.881, "recall@3": 0.726, "MRR": 0.668}


@pytest.fixture
def real_embeddings(monkeypatch):
    monkeypatch.setattr(embeddings, "embed_passages", embed_passages)
    monkeypatch.setattr(embeddings, "embed_query", embed_query)


def pdf(pages: list[str]) -> bytes:
    # Lines of about 90 characters, like a real page.
    return make_pdf(*("\n".join(textwrap.wrap(page, 90)) for page in pages))


def check_workspaces(client, db):
    """The set's workspace, and another person's with look-alike text."""
    other_id = workspace_for(client, "bob@example.com")
    for name, pages in OTHER_WORKSPACE.items():
        upload(client, other_id, name, pdf(pages))
    mine_id = workspace_for(client, "ada@example.com")
    for name, pages in DOCUMENTS.items():
        upload(client, mine_id, name, pdf(pages))
    return workspace(db, mine_id)


def scorecard(db, checked_workspace, retrieve) -> dict:
    """Every question of the set through `retrieve`, scored."""
    retrieve(db, checked_workspace, "warm up")  # loads the model before timing
    rows = []
    for question, kind, answers in QUESTIONS:
        start = time.perf_counter()
        passages = retrieve(db, checked_workspace, question)
        milliseconds = (time.perf_counter() - start) * 1000

        assert len(passages) <= PASSAGES
        # Workspace isolation: only this workspace's documents, ever.
        assert {passage["filename"] for passage in passages} <= set(DOCUMENTS), question
        pages = [(passage["filename"], passage["page_number"]) for passage in passages]
        ranks = [pages.index(answer) + 1 for answer in answers if answer in pages]
        rows.append(
            {
                "question": question,
                "kind": kind,
                "recall@6": len(ranks) / len(answers),
                "recall@3": sum(rank <= 3 for rank in ranks) / len(answers),
                "hit@1": float(1 in ranks),
                "rr": 1 / min(ranks) if ranks else 0.0,
                "all parts": float(len(ranks) == len(answers)),
                "ms": milliseconds,
            }
        )
    return {"rows": rows, "kinds": _summaries(rows)}


def _summaries(rows: list[dict]) -> dict:
    def summary(group):
        return {
            "questions": len(group),
            "recall@6": round(statistics.mean(r["recall@6"] for r in group), 3),
            "recall@3": round(statistics.mean(r["recall@3"] for r in group), 3),
            "hit@1": round(statistics.mean(r["hit@1"] for r in group), 3),
            "MRR": round(statistics.mean(r["rr"] for r in group), 3),
            "all parts": round(statistics.mean(r["all parts"] for r in group), 3),
            "median ms": round(statistics.median(r["ms"] for r in group)),
        }

    kinds = {kind: summary([r for r in rows if r["kind"] == kind]) for kind in dict.fromkeys(r["kind"] for r in rows)}
    return {**kinds, "all": summary(rows)}


def show(card: dict) -> None:
    columns = ["questions", "recall@6", "recall@3", "hit@1", "MRR", "all parts", "median ms"]
    print("\n" + f"{'':10}" + "".join(f"{c:>11}" for c in columns))
    for kind, summary in card["kinds"].items():
        print(f"{kind:10}" + "".join(f"{summary[c]:>11}" for c in columns))
    print("Answer pages not among the passages:")
    for row in card["rows"]:
        if row["recall@6"] < 1:
            print(f"  [{row['kind']}] {row['question']} (recall {row['recall@6']:.2f})")


def test_retrieval_scores_at_least_the_baseline(client, db, real_embeddings):
    checked_workspace = check_workspaces(client, db)

    card = scorecard(db, checked_workspace, _find_passages)

    show(card)
    if BASELINE is not None:
        for score in ("recall@6", "recall@3", "MRR"):
            assert card["kinds"]["all"][score] >= BASELINE[score], score
