"""Which sentences of an answer its sources back (V0.9). Rules, no AI: a
sentence needs a citation, and every number in it must be in a passage it
cites. A calculation ("about 1,533 a month" from "18,400 a year") or a
conclusion without a citation isn't backed by the documents, even when it is
right, so the person is told.
"""

import re

# "[1]" markers (citations are already split into single markers).
MARKER = re.compile(r"\[(\d+)\]")
# Numbers such as 500, 18,400, 1.5, 192.168.8.1. Not the digits of a code
# written after letters ("AX-500", "AX500"): a name, not a quantity. "12V" and
# "3-year" start with their number, so they still count.
NUMBER = re.compile(r"(?<![\w.,])(?<![A-Za-z]-)\d+(?:[.,]\d+)*")
# A sentence ends at . ! or ? followed by a space ("192.168.8.1" has none).
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

NO_SOURCE = "no_source"
NUMBER_NOT_IN_SOURCE = "number_not_in_source"


def sentences(answer: str) -> list[str]:
    return [sentence for sentence in SENTENCE_END.split(answer.strip()) if sentence]


def numbers(text: str) -> set[str]:
    """The numbers in a text, without the [n] markers, thousands commas
    removed so "18,400" and "18400" are the same number."""
    return {number.replace(",", "") for number in NUMBER.findall(MARKER.sub("", text))}


def unsupported_numbers(sentence: str, passages: dict[int, str]) -> set[str]:
    """Numbers in the sentence that aren't in any passage it cites. With no
    citation, every number is unsupported: nothing backs it."""
    cited = [passages[int(n)] for n in MARKER.findall(sentence) if int(n) in passages]
    found = set().union(*(numbers(text) for text in cited))
    return numbers(sentence) - found


def unsupported_sentences(answer: str, passages: dict[int, str]) -> list[dict]:
    """The answer's sentences its sources don't back, in reading order: with
    no citation (`no_source`), or with a number the cited passages don't
    contain (`number_not_in_source`, with those numbers as written)."""
    flagged = []
    for sentence in sentences(answer):
        if not MARKER.search(sentence):
            flagged.append({"sentence": sentence, "reason": NO_SOURCE, "numbers": []})
            continue
        missing = unsupported_numbers(sentence, passages)
        if missing:
            written = NUMBER.findall(MARKER.sub("", sentence))
            shown = list(dict.fromkeys(n for n in written if n.replace(",", "") in missing))
            flagged.append({"sentence": sentence, "reason": NUMBER_NOT_IN_SOURCE, "numbers": shown})
    return flagged
