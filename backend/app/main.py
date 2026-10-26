import logging
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import actions, auth, compare, documents, facts, health, qa, search, workspaces
from app.core.config import settings
from app.core.logs import setup_logging
from app.documents import embeddings, reranking
from app.services.documents import fail_interrupted_documents, open_session

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)
request_logger = logging.getLogger("app.requests")


def load_models() -> None:
    """Loads the local embedding model and reranker (downloading them the
    first time), so the first search or question after a start doesn't wait
    for it. A failure (no internet for the first download, say) is logged:
    the models then load on first use, as before."""
    try:
        embeddings.embed_query("warm up")
        reranking.relevance("warm up", ["warm up"])
    except Exception:
        logger.exception("Couldn't load the AI models at start-up; they will load on first use")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On start-up: documents left "processing" by a previous run will never
    # finish (their background job died with that run), so mark them failed.
    with open_session() as db:
        fail_interrupted_documents(db)
    # In the background: the server answers requests straight away, and
    # anything that needs a model before it's loaded just waits for it.
    threading.Thread(target=load_models, name="load-models", daemon=True).start()
    yield


app = FastAPI(title="Aletheia", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """One line per request: method, path, status, time taken and a short
    request id, also sent back as X-Request-ID, so a reported error can be
    found in the log. The path only: the query (?q=…) can hold what someone
    searched for, which doesn't belong in a log."""
    request_id = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        # A bug: logged with its traceback and id, and the person gets a
        # plain 500 carrying the same id.
        request_logger.exception(
            "%s %s failed after %d ms [%s]", request.method, request.url.path, _ms_since(start), request_id
        )
        response = JSONResponse({"detail": "Internal Server Error"}, status_code=500)
    else:
        # Health is asked every few seconds by whatever watches the server:
        # only shown when looking closely (LOG_LEVEL=DEBUG).
        level = logging.DEBUG if request.url.path == "/api/v1/health" else logging.INFO
        request_logger.log(
            level,
            "%s %s %d %d ms [%s]",
            request.method,
            request.url.path,
            response.status_code,
            _ms_since(start),
            request_id,
        )
    response.headers["X-Request-ID"] = request_id
    return response


def _ms_since(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)

# Sent with every response. nosniff: browsers use the declared type, so an
# uploaded file can't be run as a script or page. frame-ancestors / DENY: no
# other site can show Aletheia inside a frame (clickjacking). Referrer: links
# out don't carry Aletheia's addresses (they contain workspace ids).
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "frame-ancestors 'none'",
    "Referrer-Policy": "same-origin",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    return response


app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(workspaces.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(qa.router, prefix="/api/v1")
app.include_router(facts.router, prefix="/api/v1")
app.include_router(compare.router, prefix="/api/v1")
app.include_router(actions.router, prefix="/api/v1")
