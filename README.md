# Aletheia

A document intelligence workspace: upload documents, make them searchable, and
get answers backed by evidence from the source — not just AI-generated text.

## Status

**V0.1 — Foundation (done).** Accounts, sign in and workspaces, in the backend
and the frontend.

**V0.2 — Processing (done).** Upload PDF and DOCX files into a workspace; their
text is extracted page by page (PDF) or section by section (Word) in the
background, with OCR for scanned pages.

**V0.3 — Search (done).** Documents are cut into chunks (page headers and
footers left out) and embedded with a local model. Search a workspace by
meaning (pgvector) or by exact words (PostgreSQL full-text search); every result
shows its page or section, and PDF results open at that page.

**V0.4 — Grounded Q&A (done).** One question box per workspace. **Ask** writes
a short answer from the workspace's most relevant passages (Gemini), and every
claim carries a numbered source that shows the passage and opens its page.
Citations are checked by the backend: a source that wasn't among the passages
is removed, and an answer without any real source is replaced by "the documents
don't answer this". **Find passages** lists the matching passages, without AI.

**Next — V0.5: structured intelligence.** Names, dates, requirements and tables
pulled out of documents, each with its source.

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy, Alembic, Pydantic
- **Database:** PostgreSQL + pgvector (vector search), full-text search
- **AI:** local embedding model (`BAAI/bge-small-en-v1.5` via fastembed), Tesseract OCR,
  Google Gemini for answers (`google-genai`)
- **Frontend:** React, TypeScript, Vite, Tailwind CSS

## Run the backend locally

Requirements: Python 3.11+, PostgreSQL with the
[pgvector](https://github.com/pgvector/pgvector) extension, and Tesseract for
reading scanned PDFs (OCR). On Windows: `winget install --id UB-Mannheim.TesseractOCR`.
Without Tesseract everything else works; scanned PDFs are marked as failed.

pgvector has no Windows installer; build it once from an administrator
"x64 Native Tools Command Prompt for VS" (needs Visual Studio's
"Desktop development with C++"):

```bat
set "PGROOT=C:\Program Files\PostgreSQL\17"
git clone --branch v0.8.7 https://github.com/pgvector/pgvector.git
cd pgvector
nmake /F Makefile.win
nmake /F Makefile.win install
```

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
python -m app.backfill          # once, after upgrading to V0.3: chunk and embed older documents
uvicorn app.main:app --reload   # http://localhost:8000/api/v1/health
pytest                          # run tests
```

The first document processed downloads the embedding model
(`BAAI/bge-small-en-v1.5`, about 67 MB) into `backend/models/`. It runs on
the CPU; uploading, reading and searching documents never uses an outside service.

Answers to questions are written by Google Gemini. Get a free API key at
[aistudio.google.com](https://aistudio.google.com) and add `GEMINI_API_KEY=...`
to `backend/.env`. Only the question and the few passages chosen to answer it
are sent; on Gemini's free tier Google may use them to improve its products, so
use the free tier with test documents only. Without a key everything else works
and Ask shows "Couldn't write an answer right now". `LLM_MODEL` and
`LLM_FALLBACK_MODEL` choose the models (see `.env.example`).

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
