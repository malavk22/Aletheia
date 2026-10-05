from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.documents import embeddings
from app.models.document import Document, DocumentChunk, DocumentPart
from app.models.workspace import Workspace


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
        .order_by(score.desc())
        .limit(limit)
    ).all()
    return [
        {
            "document_id": chunk.document_id,
            "filename": filename,
            "chunk_position": chunk.position,
            "page_number": page_number,
            "heading": heading,
            "source": source,
            "text": chunk.text,
            "score": round(score, 3),
        }
        for chunk, filename, page_number, heading, source, score in rows
    ]
