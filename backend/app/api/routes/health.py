import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.documents import embeddings, reranking

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """Asked by whatever watches the server (Docker, in step 4). 503 when the
    database can't be reached: the app can't work without it. The models
    still loading isn't a failure, only slower first answers, so it's
    reported but stays 200."""
    models = "ready" if _loaded(embeddings._model) and _loaded(reranking._model) else "loading"
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Health check: the database can't be reached")
        return JSONResponse(
            {"status": "error", "database": "down", "models": models}, status_code=503
        )
    return {"status": "ok", "database": "ok", "models": models}


def _loaded(model) -> bool:
    # Each model is made once and kept by lru_cache: loaded once it's there.
    return model.cache_info().currsize > 0
