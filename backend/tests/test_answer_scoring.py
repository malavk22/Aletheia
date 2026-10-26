import pytest
from answer_scoring import contains, score_answer, states

from app.qa.support import numbers, sentences, unsupported_numbers

NOT_FOUND = "The documents in this workspace don't answer this question."


# Dates: the same date written in another order still matches; another date doesn't.


@pytest.mark.parametrize(
    "text, fact",
    [
        ("Ravi will contact the provider by March 20.", "20 March"),
        ("Ravi will contact the provider by 20 March.", "March 20"),
        ("The launch moved to April 12, 2026.", "12 April 2026"),
        ("The launch moved to 12 April 2026.", "April 12, 2026"),
        ("The launch moved to April 12, 2026.", "12 April"),
        ("It starts on 1 FEBRUARY 2026.", "February 1, 2026"),
    ],
)
def test_the_same_date_in_another_order_matches(text, fact):
    assert contains(text, fact)


@pytest.mark.parametrize(
    "text, fact",
    [
        # Another day, another month, another year.
        ("Ravi will contact the provider by March 21.", "20 March"),
        ("Ravi will contact the provider by May 20.", "20 March"),
        ("The launch moved to April 12, 2027.", "12 April 2026"),
        # A day that is part of another day.
        ("The launch moved to 12 March.", "2 March"),
        ("The launch moved to March 12.", "March 2"),
    ],
)
def test_a_different_date_does_not_match(text, fact):
    assert not contains(text, fact)


# Facts are found as whole words and numbers.


@pytest.mark.parametrize(
    "text, fact, found",
    [
        ("a late fee of 500 rupees per day", "500", True),
        ("a fee of 1,500 rupees", "500", False),
        ("leave in 2024", "24", False),
        ("a premium of 18,400 rupees", "18", False),
        ("a 1.5 A adapter", "5", False),
        ("Kestrel Cloud was chosen.", "kestrel cloud", True),
        ("The address is 192.168.8.1.", "192.168.8.1", True),
    ],
)
def test_facts_match_whole_words_and_numbers(text, fact, found):
    assert contains(text, fact) is found


def test_a_fact_can_be_written_several_ways():
    assert states("two months of notice", ("2 months", "two months"))
    assert not states("one month of notice", ("2 months", "two months"))


# Sentences, numbers and their sources.


def test_sentences_split_at_full_stops_but_not_inside_addresses():
    answer = "The address is 192.168.8.1 [1]. The other is 192.168.10.1 [2]."

    assert sentences(answer) == ["The address is 192.168.8.1 [1].", "The other is 192.168.10.1 [2]."]


def test_numbers_ignore_markers_and_thousands_commas():
    assert numbers("A fee of 18,400 rupees [2], or 1,533.33 a month [1].") == {"18400", "1533.33"}


def test_the_digits_of_a_product_code_are_not_numbers():
    assert numbers("The AX-500 and the AX300 [1].") == set()
    # Quantities still count, also when a unit follows.
    assert numbers("A 12V adapter with a 3-year warranty.") == {"12", "3"}
    assert numbers("Between 60-90 days.") == {"60", "90"}


def test_a_calculated_number_is_unsupported():
    passages = {2: "Annual premium: 18,400 rupees, including taxes."}
    sentence = "The premium is 18,400 rupees, approximately 1,533.33 rupees per month [2]."

    assert unsupported_numbers(sentence, passages) == {"1533.33"}


def test_a_reordered_date_is_supported_but_a_different_date_is_not():
    passages = {1: "Ravi will contact the gateway provider by 20 March."}

    assert unsupported_numbers("Ravi will call by March 20 [1].", passages) == set()
    assert unsupported_numbers("Ravi will call by March 21 [1].", passages) == {"21"}


def test_numbers_in_a_sentence_without_a_citation_are_unsupported():
    passages = {1: "The rent is 28,000 rupees per month."}

    assert unsupported_numbers("So the rent is 28,000 a month.", passages) == {"28000"}


def test_a_number_must_be_in_the_passage_the_sentence_cites():
    passages = {1: "The rent is 28,000 rupees.", 2: "The deposit is 56,000 rupees."}

    assert unsupported_numbers("The deposit is 56,000 rupees [1].", passages) == {"56000"}


# One answer, scored.


def record(answer, citations, seconds=2.0):
    return {"answer": answer, "citations": citations, "seconds": seconds}


def citation(number, filename, page, text):
    return {"number": number, "filename": filename, "page_number": page, "text": text}


def test_a_correct_cited_answer_scores_full_marks():
    answer = record(
        "Ravi will contact the provider by March 20 [1].",
        [citation(1, "notes.pdf", 3, "Ravi will contact the gateway provider by 20 March.")],
    )

    scored = score_answer(answer, [("20 March",)], [("notes.pdf", 3)], NOT_FOUND)

    assert scored["facts"] == scored["answer pages cited"] == scored["facts in cited passages"] == 1.0
    assert scored["correct"] and scored["sentences cited"] == 1.0
    assert scored["uncited sentences"] == [] and scored["unsupported numbers"] == {}
    assert not scored["abstained"]


def test_a_wrong_date_is_not_a_correct_answer():
    answer = record(
        "Ravi will contact the provider by March 21 [1].",
        [citation(1, "notes.pdf", 3, "Ravi will contact the gateway provider by 20 March.")],
    )

    scored = score_answer(answer, [("20 March",)], [("notes.pdf", 3)], NOT_FOUND)

    assert not scored["correct"]
    assert scored["unsupported numbers"] == {"Ravi will contact the provider by March 21 [1].": ["21"]}


def test_an_uncited_conclusion_is_reported():
    answer = record(
        "The AX-500 supports 128 devices [1]. The AX-300 supports 64 [2]. So the AX-500 supports more.",
        [
            citation(1, "ax500.pdf", 1, "It supports up to 128 connected devices."),
            citation(2, "ax300.pdf", 1, "It supports up to 64 connected devices."),
        ],
    )

    scored = score_answer(answer, [("128",), ("64",)], [("ax500.pdf", 1), ("ax300.pdf", 1)], NOT_FOUND)

    assert scored["correct"]
    assert scored["uncited sentences"] == ["So the AX-500 supports more."]
    assert scored["sentences cited"] == pytest.approx(2 / 3)


def test_a_fact_not_in_the_cited_passage_is_counted():
    # The answer is right, but the passage it cites doesn't say it.
    answer = record("The fee is 500 rupees [1].", [citation(1, "lease.pdf", 1, "The tenant pays rent monthly.")])

    scored = score_answer(answer, [("500",)], [("lease.pdf", 2)], NOT_FOUND)

    assert scored["facts"] == 1.0
    assert scored["facts in cited passages"] == 0.0
    assert scored["answer pages cited"] == 0.0


def test_abstaining_on_an_answerable_question_is_counted():
    scored = score_answer(record(NOT_FOUND, []), [("500",)], [("lease.pdf", 2)], NOT_FOUND)

    assert scored["abstained"] and not scored["correct"]
