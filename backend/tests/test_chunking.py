from app.documents.chunking import chunk_text


def sentences(count):
    return [f"Sentence number {n} is here." for n in range(1, count + 1)]


def test_short_text_is_one_chunk_with_tidy_spaces():
    assert chunk_text("The tenant pays\nrent   monthly.") == [
        "The tenant pays rent monthly."
    ]


def test_empty_text_gives_no_chunks():
    assert chunk_text("") == []
    assert chunk_text(" \n\n ") == []


def test_long_text_is_cut_between_sentences_and_nothing_is_lost():
    all_sentences = sentences(100)

    chunks = chunk_text(" ".join(all_sentences), size=200, overlap=50)

    assert len(chunks) > 1
    assert all(len(chunk) <= 200 for chunk in chunks)
    # Every chunk starts and ends on a whole sentence...
    assert all(chunk.startswith("Sentence") and chunk.endswith(".") for chunk in chunks)
    # ...and every sentence is in some chunk.
    assert all(any(s in chunk for chunk in chunks) for s in all_sentences)


def test_next_chunk_repeats_the_end_of_the_previous_one():
    chunks = chunk_text(" ".join(sentences(20)), size=200, overlap=50)

    for previous, following in zip(chunks, chunks[1:]):
        last_sentence = previous.rsplit(". ", 1)[-1]
        assert following.startswith(last_sentence)


def test_no_overlap_when_turned_off():
    chunks = chunk_text(" ".join(sentences(20)), size=200, overlap=0)

    joined = " ".join(chunks)
    assert joined == " ".join(sentences(20))


def test_paragraphs_are_kept_together_when_they_fit():
    first = "First paragraph. " + "It talks about rent. " * 4
    second = "Second paragraph. " + "It talks about repairs. " * 4

    chunks = chunk_text(first + "\n\n" + second, size=150, overlap=0)

    assert chunks == [first.strip(), second.strip()]


def test_word_longer_than_a_chunk_is_cut():
    long_word = "x" * 250

    chunks = chunk_text(long_word, size=100, overlap=0)

    assert chunks == ["x" * 100, "x" * 100, "x" * 50]
