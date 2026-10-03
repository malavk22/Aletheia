"""Chunk and embed documents processed before V0.3.

Run once from the backend folder:  python -m app.backfill
"""

from app.services.documents import backfill_chunks, open_session

if __name__ == "__main__":
    with open_session() as db:
        count = backfill_chunks(db)
    print(f"Embedded {count} chunks.")
