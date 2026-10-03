import math

# Imported before the fake_embeddings fixture replaces them, so these are the
# real model functions. The model is downloaded on the very first run.
from app.documents.embeddings import embed_passages, embed_query


def similarity(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_vectors_have_384_numbers_and_unit_length():
    vector = embed_query("When does the lease end?")

    assert len(vector) == 384
    assert math.isclose(math.sqrt(similarity(vector, vector)), 1.0, abs_tol=1e-3)


def test_one_vector_per_text_in_order():
    vectors = embed_passages(["The rent is due monthly.", "The tenant has a dog."])

    assert len(vectors) == 2
    assert vectors[0] != vectors[1]


def test_similar_meaning_scores_higher_even_with_different_words():
    question = embed_query("When can the agreement be terminated?")
    ending, rent = embed_passages(
        [
            "Either party may end this contract with 30 days written notice.",
            "The rent is due on the first day of each month.",
        ]
    )

    # No shared key words with the question, but the same meaning.
    assert similarity(question, ending) > similarity(question, rent)
