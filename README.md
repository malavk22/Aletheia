# Aletheia

A document intelligence workspace: upload documents, make them searchable, and
get answers backed by evidence from the source — not just AI-generated text.

## Status

**V0.1 — Foundation (in progress).** Backend: accounts, login and workspaces.
Frontend: project setup and design foundation.

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy, Alembic, Pydantic
- **Database:** PostgreSQL (pgvector planned)
- **Frontend:** React, TypeScript, Vite, Tailwind CSS

## Run the backend locally

Requirements: Python 3.11+, PostgreSQL.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

Create a database named `aletheia`, then copy `.env.example` to `.env` and set
your database password. (If the password contains `@`, write it as `%40`.)

```bash
alembic upgrade head            # create the database tables
uvicorn app.main:app --reload   # http://localhost:8000/api/v1/health
pytest                          # run tests
```

## Run the frontend locally

Requirements: Node.js 22+. Start the backend first.

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

Calls to `/api` are forwarded to the backend on port 8000 (see `vite.config.ts`).
