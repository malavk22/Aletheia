"""The answer evaluation (V0.9): the recorded Gemini answers
(recorded_answers.json, made by record_answers.py) scored with rules by
answer_scoring.py. Offline: no Gemini call, same result every run.

Run with -s to see the scorecard: pytest tests/test_answers.py -s
"""

import json
from pathlib import Path

from answer_scoring import scorecard
from answer_set import ANSWERABLE, UNANSWERABLE

from app.services.qa import NOT_FOUND

RECORDED = Path(__file__).parent / "recorded_answers.json"

# Recorded on 2026-10-26 from the answers of 2026-10-24 and 2026-10-26: what
# a new recording (after a change to the prompt or retrieval) or a change to
# the scoring rules must not fall below. Median 2.85 s, max 4.8 s a question.
AT_LEAST = {
    "facts": 1.0,
    "correct": 1.0,
    "answer pages cited": 1.0,
    "facts in cited passages": 1.0,
    "sentences cited": 0.989,
    "abstained when unanswerable": 1.0,
}
# Shares of answers; lower is better.
AT_MOST = {
    "answers with an uncited sentence": 0.033,
    "answers with an unsupported number": 0.033,
    "wrongly abstained": 0.0,
}


def show(card: dict) -> None:
    print()
    for name, value in card["totals"].items():
        print(f"  {name:36} {value}")
    for question, row in card["rows"].items():
        if not row["correct"]:
            print(f"  NOT CORRECT: {question}")
        for sentence in row["uncited sentences"]:
            print(f"  UNCITED: {sentence}")
        for sentence, found in row["unsupported numbers"].items():
            print(f"  UNSUPPORTED {found}: {sentence}")


def test_every_question_of_the_set_has_a_recorded_answer():
    # A question added to the set without recording it would be left out of
    # the scores without anyone noticing.
    recorded = json.loads(RECORDED.read_text(encoding="utf-8"))

    assert set(recorded) == {q for q, *_ in ANSWERABLE} | set(UNANSWERABLE)


def test_answers_score_at_least_the_baseline():
    recorded = json.loads(RECORDED.read_text(encoding="utf-8"))

    card = scorecard(recorded, ANSWERABLE, UNANSWERABLE, NOT_FOUND)

    show(card)
    totals = card["totals"]
    for name, floor in AT_LEAST.items():
        assert totals[name] >= floor, name
    for name, ceiling in AT_MOST.items():
        assert totals[name] <= ceiling, name
