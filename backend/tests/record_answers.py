"""Records real Gemini answers for the answer set (V0.9), to be scored
offline as often as needed without calling Gemini again.

Not collected by the normal test run (the file name doesn't start with
"test_"); run it on purpose, from backend/:

    pytest tests/record_answers.py -s

It uses the real embedding model, reranker and Gemini key (from .env), and
only the made-up check-set documents. Answers are saved after each one, and
questions already in the file are skipped, so a run stopped by Gemini's
daily limit continues where it left off the next day. Re-record (delete the
file) only when the prompt or retrieval changes.
"""

import json
import time
from datetime import date
from pathlib import Path

import pytest
from answer_set import ANSWERABLE, UNANSWERABLE
from test_retrieval import check_workspaces, real_embeddings  # noqa: F401

from app.core.config import Settings, settings
from app.qa import llm
from app.services.qa import answer_question

RECORDED = Path(__file__).parent / "recorded_answers.json"
# Gemini's free tier allows 5 requests a minute per model.
SECONDS_BETWEEN_CALLS = 13


def load() -> dict:
    return json.loads(RECORDED.read_text(encoding="utf-8")) if RECORDED.exists() else {}


def test_record_answers(client, db, real_embeddings, monkeypatch):
    # conftest removes the key from every test; this one needs the real one.
    key = Settings().gemini_api_key
    if not key:
        pytest.skip("No GEMINI_API_KEY in .env")
    monkeypatch.setattr(settings, "gemini_api_key", key)

    recorded = load()
    todo = [q for q, *_ in ANSWERABLE] + UNANSWERABLE
    todo = [question for question in todo if question not in recorded]
    print(f"\n{len(recorded)} recorded, {len(todo)} to go")
    if not todo:
        return

    checked_workspace = check_workspaces(client, db)
    for index, question in enumerate(todo):
        if index:
            time.sleep(SECONDS_BETWEEN_CALLS)
        start = time.perf_counter()
        try:
            result = answer_question(db, checked_workspace, question)
        except llm.LLMError as error:
            print(f"Stopped ({error.kind}, retry after {error.retry_after} s): {question}")
            break
        recorded[question] = {
            "answer": result["answer"],
            "citations": [
                {field: citation[field] for field in ("number", "filename", "page_number", "text")}
                for citation in result["citations"]
            ],
            "seconds": round(time.perf_counter() - start, 1),
            "recorded_on": date.today().isoformat(),
        }
        RECORDED.write_text(json.dumps(recorded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[{len(recorded)}] {recorded[question]['seconds']} s  {question}")
    print(f"{len(recorded)} of {len(ANSWERABLE) + len(UNANSWERABLE)} recorded")
