from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import auth, documents, health, workspaces
from app.services.documents import fail_interrupted_documents, open_session


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On start-up: documents left "processing" by a previous run will never
    # finish (their background job died with that run), so mark them failed.
    with open_session() as db:
        fail_interrupted_documents(db)
    yield


app = FastAPI(title="Aletheia", lifespan=lifespan)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(workspaces.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
