from sqlalchemy import ColumnElement, cast, func, select
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.orm import Session

from app.documents import embeddings
from app.models.document import Document, DocumentChunk, DocumentPart
from app.models.workspace import Workspace

# A word found in more than this share of a workspace's chunks says little
# about which chunk answers a question. A first guess: on a 48-page report
# "project" was in 36 of 92 chunks, "hosted" in 14 and "guide" in 4.
COMMON_SHARE = 0.25


def semantic_search(db: Session, workspace: Workspace, query: str, limit: int):
    """The chunks in this workspace closest in meaning to `query`, closest
    first, each with its document and location.

    Closeness is cosine distance between the question's vector and each
    chunk's vector: 0 = same direction (same meaning), up to 2 = opposite.
    The score returned is 1 - distance, so higher is better.
    """
    vector = embeddings.embed_query(query)
    distance = DocumentChunk.embedding.cosine_distance(vector)
    return _search(
        db,
        workspace,
        score=1 - distance,
        match=DocumentChunk.embedding.is_not(None),
        limit=limit,
    )


def keyword_search(db: Session, workspace: Workspace, query: str, limit: int):
    """The chunks in this workspace that contain the words of `query`, best
    match first.

    Words are compared by their stems, so "terminate" also finds "terminated"
    and "termination". The query understands web-search style: "quoted
    phrase", or, -excluded. The score is PostgreSQL's text rank: higher means
    the words appear more often and closer together. It is not on the same
    scale as the semantic score.
    """
    words = func.websearch_to_tsquery("english", query)
    return _search(
        db,
        workspace,
        score=func.ts_rank_cd(DocumentChunk.search_words, words),
        match=DocumentChunk.search_words.bool_op("@@")(words),
        limit=limit,
    )


def rare_word_search(db: Session, workspace: Workspace, query: str, limit: int):
    """The chunks containing any of the question's rare words, best first.

    Questions are full of words that say little: "who", "the" (PostgreSQL
    ignores these already), and words found all over this workspace, such as
    "project" in a project report. Only words in at most COMMON_SHARE of the
    workspace's chunks are searched for, and a chunk needs just one of them,
    so a word missing from the documents ("mentor") doesn't block one that is
    there ("guide")."""
    total = _count_chunks(db, workspace)
    rare = [
        word
        for word in _words(db, query)
        # max(1, …): in a tiny workspace a word found once still counts.
        if 0 < _count_chunks(db, workspace, _contains(_any_of([word]))) <= max(1, total * COMMON_SHARE)
    ]
    if not rare:
        return []
    words = _any_of(rare)
    return _search(
        db,
        workspace,
        score=func.ts_rank_cd(DocumentChunk.search_words, words),
        match=_contains(words),
        limit=limit,
    )


def _words(db: Session, query: str) -> list[str]:
    """The question's words exactly as PostgreSQL stores the documents' words,
    so they can match: "192.168.8.1" stays one word, "AX-300" gives "ax" and
    "-300", "claims" becomes "claim". A slash is also read as a space,
    because PostgreSQL takes "mentor/guide" for one word (a file path)."""
    vector = func.to_tsvector("english", query).op("||")(
        func.to_tsvector("english", query.replace("/", " "))
    )
    return list(db.scalars(select(func.unnest(func.tsvector_to_array(vector)))))


def _any_of(words: list[str]) -> ColumnElement:
    """A search for chunks containing any of these stored words, as they are
    (they are already stemmed, so they aren't parsed again)."""
    quoted = ["'" + word.replace("\\", "\\\\").replace("'", "''") + "'" for word in words]
    return cast(" | ".join(quoted), TSQUERY)


def _contains(words: ColumnElement) -> ColumnElement[bool]:
    return DocumentChunk.search_words.bool_op("@@")(words)


def _count_chunks(db: Session, workspace: Workspace, *conditions) -> int:
    return db.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.workspace_id == workspace.id, *conditions)
    )


def _search(
    db: Session,
    workspace: Workspace,
    score: ColumnElement[float],
    match: ColumnElement[bool],
    limit: int,
):
    """Chunks of this workspace that pass `match`, highest `score` first,
    each with its document and location."""
    rows = db.execute(
        select(
            DocumentChunk,
            Document.filename,
            DocumentPart.page_number,
            DocumentPart.heading,
            DocumentPart.source,
            score.label("score"),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(
            DocumentPart,
            (DocumentPart.document_id == DocumentChunk.document_id)
            & (DocumentPart.position == DocumentChunk.part_position),
        )
        # Only this workspace's documents, filtered inside the query itself,
        # so other workspaces' text is never even read.
        .where(Document.workspace_id == workspace.id, match)
        # Equal scores are common in keyword search; without a tie-breaker
        # PostgreSQL returns them in any order, so the same question could
        # find different passages from one run to the next.
        .order_by(score.desc(), Document.filename, DocumentChunk.position)
        .limit(limit)
    ).all()
    return [
        {
            "document_id": chunk.document_id,
            "filename": filename,
            "chunk_position": chunk.position,
            "part_position": chunk.part_position,
            "page_number": page_number,
            "heading": heading,
            "source": source,
            "text": chunk.text,
            "score": round(score, 3),
        }
        for chunk, filename, page_number, heading, source, score in rows
    ]
