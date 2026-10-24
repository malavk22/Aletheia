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

**V0.5 — Structured intelligence (done).** **Key facts** on every processed
document: the people, organizations, dates, amounts and requirements in it,
pulled out by Gemini as structured data. Every fact carries the document's own
sentence and its page; the backend keeps a fact only if that sentence really is
on that page, and dates are checked to be real. Facts are shown by group, with
repeats shown once. (Tables and custom fields come later.)

**V0.6 — Comparison (done).** **Compare versions** takes two documents of a
workspace and lists what changed, sentence by sentence and without AI: changed
(with the changed words marked), removed and added, each with its page in both
versions; formatting-only changes (spacing, capitals, punctuation) are kept
apart. **Check for conflicts** pairs the passages of the two documents that are
closest in meaning and asks Gemini which ones contradict each other; each
**potential conflict** shows both documents' own sentences and pages, and is kept
only if both sentences really are in their documents.

**V0.7 — Action layer (done).** **Actions** on every processed document: the
deadlines and tasks it asks of someone, found by Gemini, each with the
document's own sentence and page (kept only if that sentence really is on that
page). Exact dates ("by 15 March 2026") and relative deadlines ("within 30 days
of signing") are kept apart, and a date is never worked out or guessed: a
relative deadline gets a date only from a person, marked as theirs. Confidence
comes from rules on the evidence. Every action is a suggestion until a person
confirms it; confirmed actions of the whole workspace are listed as
**Upcoming** (overdue and the next 14 days), **Timeline** (by month) and **No
fixed date**. A finished action is marked **done**: it leaves Upcoming and stays
in the Timeline. Reminders are shown in the app only (no email or phone).

**V0.8 — Advanced RAG (done).** Ask finds its passages in several steps,
each kept only because it scored better on a fixed set of 42 test questions
(`backend/tests/retrieval_set.py`): search by rare words and by meaning,
combined by reciprocal rank fusion; the 20 best re-ordered by a **local
reranker** (a cross-encoder that reads the question and each passage
together); a question with several parts also searched part by part, so every
part gets a place. Share of answer pages among the 6 passages Ask reads:
0.881 → 1.0; the first passage is on an answer page 52% → 90% of the time.
**Search in** limits Ask and Find passages to chosen documents. When Gemini's
usage limit is reached, the page says so and when to try again.

**Next — V0.9: AI evaluation.** Scoring the answers themselves: citation
correctness, faithfulness and unsupported claims.

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy, Alembic, Pydantic
- **Database:** PostgreSQL + pgvector (vector search), full-text search
- **AI:** local embedding model (`BAAI/bge-small-en-v1.5` via fastembed), local reranker
  (`Xenova/ms-marco-MiniLM-L-6-v2`, a cross-encoder, via fastembed), Tesseract OCR,
  Google Gemini for answers, key facts, conflict checks and actions (`google-genai`)
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
The first question asked downloads the reranker (`Xenova/ms-marco-MiniLM-L-6-v2`,
about 80 MB) into the same folder; it also runs on the CPU, and adds 1–3 s to
an answer (more for a question with several parts).

Answers to questions are written by Google Gemini. Get a free API key at
[aistudio.google.com](https://aistudio.google.com) and add `GEMINI_API_KEY=...`
to `backend/.env`. Only the question and the few passages chosen to answer it
are sent; on Gemini's free tier Google may use them to improve its products, so
use the free tier with test documents only. Key facts also use Gemini and send
the whole document's text, only when you click "Key facts" on a document not
extracted before, or "Extract again" (a 50-page report takes about a minute).
Check for conflicts sends up to 8 pairs of matched passages (about 12,000
characters), only when you click it; comparing versions never uses Gemini.
Actions send the whole document's text, like Key facts, only when you click
"Actions" on a document not searched before, or "Find again"; the workspace's
Upcoming and Timeline lists never call Gemini.
Without a key everything else works; Ask, Key facts, Check for conflicts and
Actions show "Couldn't … right now". `LLM_MODEL` and `LLM_FALLBACK_MODEL` choose the models (see `.env.example`).

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
