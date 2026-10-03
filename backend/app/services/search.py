from sqlalchemy import select
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
    rows = db.execute(
        select(
            DocumentChunk,
            Document.filename,
            DocumentPart.page_number,
            DocumentPart.heading,
            DocumentPart.source,
            distance.label("distance"),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(
            DocumentPart,
            (DocumentPart.document_id == DocumentChunk.document_id)
            & (DocumentPart.position == DocumentChunk.part_position),
        )
        # Only this workspace's documents, filtered inside the query itself,
        # so other workspaces' text is never even read.
        .where(
            Document.workspace_id == workspace.id,
            DocumentChunk.embedding.is_not(None),
        )
        .order_by(distance)
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
            "score": round(1 - distance, 3),
        }
        for chunk, filename, page_number, heading, source, distance in rows
    ]
