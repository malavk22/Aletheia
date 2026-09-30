from fastapi import FastAPI

from app.api.routes import auth, health

app = FastAPI(title="Aletheia")

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
