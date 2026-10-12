import re

# How many non-blank lines at the top and at the bottom of a page are checked
# for headers and footers.
EDGE_LINES = 2
# A line at the edge of this many pages (or more) is a header or footer. Three,
# not a share of all pages: chapter headers ("CHAPTER 4 SYSTEM REQUIREMENTS")
# repeat only on that chapter's pages.
MIN_PAGES = 3


def repeated_edge_lines(pages: list[str]) -> set[str]:
    """The headers and footers of a document: lines that sit at the top or
    bottom of at least MIN_PAGES pages, compared with page numbers ignored.
    Returned in their compared ("key") form."""
    count: dict[str, int] = {}
    for text in pages:
        lines = text.splitlines()
        # Each line counts once per page, even if it is both top and bottom.
        for key in {_key(lines[i]) for i in _edge_positions(lines)}:
            count[key] = count.get(key, 0) + 1
    return {key for key, pages_seen in count.items() if pages_seen >= MIN_PAGES}


def remove_edge_lines(text: str, repeated: set[str]) -> str:
    """The page text without its header and footer lines. Only lines at the
    top or bottom are removed: the same words in the middle of a page are
    real content."""
    lines = text.splitlines()
    remove = {i for i in _edge_positions(lines) if _key(lines[i]) in repeated}
    return "\n".join(line for i, line in enumerate(lines) if i not in remove)


def _edge_positions(lines: list[str]) -> list[int]:
    """Where the first and last EDGE_LINES non-blank lines are. A short page
    has none: with no body between them, its "top" and "bottom" lines are the
    content itself, and numbered content ("Clause 1…", "Clause 2…") would
    otherwise look like a footer once numbers are ignored."""
    filled = [i for i, line in enumerate(lines) if line.strip()]
    if len(filled) <= 2 * EDGE_LINES:
        return []
    return filled[:EDGE_LINES] + filled[-EDGE_LINES:]


def _key(line: str) -> str:
    # "Department of Computer Science And Engineering 14" and "... 23" are the
    # same footer: compare with every number replaced and spacing tidied.
    return " ".join(re.sub(r"\d+", "#", line).lower().split())
