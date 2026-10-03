# Aletheia

A document intelligence workspace: upload documents, make them searchable, and
get answers backed by evidence from the source — not just AI-generated text.

## Status

**V0.1 — Foundation (done).** Accounts, sign in and workspaces, in the backend
and the frontend.

**V0.2 — Processing.** Upload PDF and DOCX files into a workspace; their text is
extracted page by page (PDF) or section by section (Word) in the background,
with OCR for scanned pages.

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy, Alembic, Pydantic
- **Database:** PostgreSQL (pgvector planned)
- **Frontend:** React, TypeScript, Vite, Tailwind CSS

## Run the backend locally

Requirements: Python 3.11+, PostgreSQL, and Tesseract for reading scanned PDFs
(OCR). On Windows: `winget install --id UB-Mannheim.TesseractOCR`. Without
Tesseract everything else works; scanned PDFs are marked as failed.

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

Tests run in their own database, `aletheia_test`, which is created
automatically on the first run. They never touch the `aletheia` database.

## Run the frontend locally

Requirements: Node.js 22+. Start the backend first.

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

Calls to `/api` are forwarded to the backend on port 8000 (see `vite.config.ts`).
