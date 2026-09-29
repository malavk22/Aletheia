from fastapi import FastAPI

from app.api.routes import health

app = FastAPI(title="Aletheia")

app.include_router(health.router, prefix="/api/v1")
