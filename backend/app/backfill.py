"""Chunk and embed documents processed before V0.3.

Run from the backend folder:  python -m app.backfill
After a change to how chunks are made, rebuild them all:
                              python -m app.backfill --rebuild
"""

import sys

from app.services.documents import backfill_chunks, open_session

if __name__ == "__main__":
    with open_session() as db:
        count = backfill_chunks(db, rebuild="--rebuild" in sys.argv)
    print(f"Embedded {count} chunks.")
