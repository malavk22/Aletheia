from functools import lru_cache

from fastembed.rerank.cross_encoder import TextCrossEncoder

from app.core.config import settings

# A small cross-encoder that runs on the CPU, so passages never leave this
# machine. Unlike the embedding model, it reads the question and a passage
# together, so it can judge how well this passage answers this question; too
# slow for a whole workspace, fine for a short list.
MODEL_NAME = "Xenova/ms-marco-MiniLM-L-6-v2"


@lru_cache
def _model() -> TextCrossEncoder:
    # Loaded once, on first use (downloaded the very first time), then kept.
    return TextCrossEncoder(MODEL_NAME, cache_dir=settings.embedding_cache_dir)


def relevance(question: str, texts: list[str]) -> list[float]:
    """How well each text answers `question`, in the same order: higher is
    better. The numbers only compare texts for the same question."""
    # One text at a time was the fastest on a 4-core CPU, as for embeddings
    # (no padding to the longest text). Measured on 20 passages: 1.07 s one
    # at a time, 1.16 s in batches of 8, 1.36 s in batches of 64.
    return [float(score) for score in _model().rerank(question, texts, batch_size=1)]
