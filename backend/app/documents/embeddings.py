from functools import lru_cache

from fastembed import TextEmbedding

from app.core.config import settings

# A small English model that runs on the CPU, so documents never leave this
# machine and nothing is paid per use. Swapping the model (or moving to a paid
# API) only changes this file, plus a migration if the size changes.
MODEL_NAME = "BAAI/bge-small-en-v1.5"
# How many numbers the model gives for each text. The database column has the
# same size.
DIMENSIONS = 384


@lru_cache
def _model() -> TextEmbedding:
    # Loaded once, on first use (downloaded the very first time), then kept.
    return TextEmbedding(MODEL_NAME, cache_dir=settings.embedding_cache_dir)


def embed_passages(texts: list[str]) -> list[list[float]]:
    """One vector per text, in the same order. Used for document chunks."""
    # One text at a time was the fastest on a 4-core CPU: in a batch every
    # text is padded to the longest one, which wastes work. Measured on a
    # 48-page PDF (84 chunks): 11 s one at a time, 23 s in batches of 16.
    vectors = _model().passage_embed(texts, batch_size=1)
    return [vector.tolist() for vector in vectors]


def embed_query(text: str) -> list[float]:
    """The vector for a search question."""
    return next(iter(_model().query_embed(text))).tolist()
