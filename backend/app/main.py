from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.routes import actions, auth, compare, documents, facts, health, qa, search, workspaces
from app.services.documents import fail_interrupted_documents, open_session


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On start-up: documents left "processing" by a previous run will never
    # finish (their background job died with that run), so mark them failed.
    with open_session() as db:
        fail_interrupted_documents(db)
    yield


app = FastAPI(title="Aletheia", lifespan=lifespan)

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
