import re

# About 200-250 words: small enough that a chunk is about one thing, so search
# can point at the exact passage; big enough to keep a clause with its context.
CHUNK_SIZE = 1000  # characters
# Up to this much text from the end of one chunk is repeated at the start of
# the next, so a sentence near a cut can still be found with its neighbours.
CHUNK_OVERLAP = 150  # characters

# Where text may be cut, best first: between paragraphs, between sentences,
# at a line break, at a space. A finer one is used only when a piece is still
# too long.
SEPARATORS = [r"\n\s*\n", r"(?<=[.!?])\s+", r"\n", r" "]


def chunk_text(
    text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """Cut text into chunks of at most `size` characters.

    Whitespace inside a chunk is tidied to single spaces (extracted text is
    full of line breaks in the middle of sentences). Empty text gives no
    chunks.
    """
    chunks: list[str] = []
    current: list[str] = []
    for piece in _split(text, size, 0):
        if current and _length(current + [piece]) > size:
            chunks.append(" ".join(current))
            # Start the next chunk with the end of this one...
            current = _tail(current, overlap)
            # ...but drop that overlap if it would not leave room for the piece.
            while current and _length(current + [piece]) > size:
                current.pop(0)
        current.append(piece)
    if current:
        chunks.append(" ".join(current))
    return chunks


def _split(text: str, size: int, level: int) -> list[str]:
    """Break text into pieces of at most `size` characters, using the best
    separator that works."""
    # Measure tidied text, but split the original: tidying first would remove
    # the paragraph and line breaks the separators look for.
    tidy = " ".join(text.split())
    if len(tidy) <= size:
        return [tidy] if tidy else []
    if level == len(SEPARATORS):
        # One "word" longer than a whole chunk (a long URL, say): cut it.
        return [tidy[start : start + size] for start in range(0, len(tidy), size)]
    pieces = []
    for part in re.split(SEPARATORS[level], text):
        pieces.extend(_split(part, size, level + 1))
    return pieces


def _length(pieces: list[str]) -> int:
    # The length once joined with single spaces.
    return sum(len(piece) for piece in pieces) + len(pieces) - 1


def _tail(pieces: list[str], overlap: int) -> list[str]:
    """The last pieces that together fit in `overlap` characters."""
    tail: list[str] = []
    for piece in reversed(pieces):
        if _length([piece] + tail) > overlap:
            break
        tail.insert(0, piece)
    return tail
