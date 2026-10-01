from fastapi import FastAPI

from app.api.routes import auth, documents, health, workspaces

app = FastAPI(title="Aletheia")

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(workspaces.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
