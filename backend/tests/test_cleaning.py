from app.documents.cleaning import remove_edge_lines, repeated_edge_lines

# Real page bodies: different words on every page, as in a real document.
BODIES = [
    "Rent is due monthly.\nIt is paid by bank transfer.\nLate payment costs extra.",
    "Pets are allowed.\nDogs must be kept on a lead.\nCats may stay indoors.",
    "The deposit is returned.\nDamage is deducted first.\nKeys must be handed back.",
]


def clean(pages):
    repeated = repeated_edge_lines(pages)
    return [remove_edge_lines(page, repeated) for page in pages]


def test_header_and_footer_with_changing_page_numbers_are_removed():
    pages = [
        f"ACME LEASE AGREEMENT\n{body}\nPage {n} of 3"
        for n, body in enumerate(BODIES, start=1)
    ]

    assert clean(pages) == BODIES


def test_header_is_found_after_blank_lines():
    pages = [f"\n  \nACME CONFIDENTIAL\n{body}\nacme.example" for body in BODIES]

    assert [page.strip() for page in clean(pages)] == BODIES


def test_line_on_only_two_pages_is_kept():
    pages = [
        f"Chapter 1 Intro\n{BODIES[0]}\nEnd.",
        f"Chapter 1 Intro\n{BODIES[1]}\nFin.",
        f"Chapter 2 Terms\n{BODIES[2]}\nStop.",
    ]

    # "chapter # intro" repeats on 2 pages and "chapter # terms" on 1: below
    # the 3-page minimum, so both could be real content.
    assert clean(pages) == pages


def test_same_words_in_the_middle_of_a_page_are_kept():
    pages = [f"Acme Ltd\n{body}\nThe end." for body in BODIES]
    middle = "Top one.\nTop two.\nAcme Ltd\nBottom one.\nBottom two."

    # Removed where it is a header (top of the first three pages), kept mid-page.
    assert clean(pages + [middle])[3] == middle


def test_short_pages_are_never_changed():
    # Once numbers are ignored these lines all look alike, but on a page this
    # short they are the content, not a header or footer.
    pages = [f"Clause {n} about rent." for n in range(1, 6)]

    assert clean(pages) == pages


def test_fewer_than_three_pages_change_nothing():
    pages = [f"Acme Ltd\n{body}\nThe end." for body in BODIES[:2]]

    assert clean(pages) == pages
