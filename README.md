# Aletheia

**Ask your documents questions and get answers you can check.**

Aletheia is a document intelligence workspace. Upload PDF and Word files, then
search them, ask questions, extract key facts and deadlines, and compare
versions. Every answer points to the exact page it came from, and anything the
sources don't back is marked as such, so you never have to take the AI's word
for it.

## Features

**Ask questions, with sources**
- Answers are written by an LLM only from your documents, with numbered
  citations that show the passage and open the page.
- Citations are verified by the backend: a reference to a passage that wasn't
  given to the model is removed, and an answer without a real source becomes
  "the documents don't answer this question".
- Each sentence is checked against the passages it cites. A sentence with no
  citation, or with a number its sources don't contain (such as a
  calculation), is listed under the answer as **Not found in the sources**.
- Questions with several parts, and questions comparing documents ("who must
  give longer notice, an employee or a contractor?"), are answered from every
  document involved.
- **Search in** limits a question to chosen documents, or to a range of pages or
  sections of one document.

**Search**
- **Find passages** by meaning or by exact words, without AI. Every result shows
  its page or section, and PDF results open at that page.

**Extract**
- **Key facts:** people, organizations, dates, amounts and requirements, each
  with the document's own sentence and page. A fact is kept only if that
  sentence really is on that page.
- **Actions:** deadlines and tasks found in a document. Exact dates and relative
  deadlines ("within 30 days of signing") are kept apart; a date is never
  guessed. Actions are suggestions until a person confirms them, then appear in
  the workspace's **Upcoming** list and **Timeline**.

**Compare**
- **Compare versions:** what changed between two documents, sentence by
  sentence (changed words marked, formatting-only changes kept apart), without AI.
- **Check for conflicts:** passages on the same topic in two documents, and the
  ones that contradict each other, with both sentences and pages.

**Documents and workspaces**
- PDF and DOCX upload, processed in the background; scanned pages are read
  with OCR.
- Accounts and workspaces. Every query is scoped to the workspace in the
  database itself: documents of other workspaces can't be searched, cited or
  opened, and asking for one returns "not found".

## How it works

```
Upload ─► extract text (OCR for scanned pages) ─► split into chunks ─► embed locally
                                                                          │
Question ─► keyword search ─┐                                             ▼
          ─► meaning search ─┴► rank fusion ─► local reranker ─► best 6 passages
                                                                          │
                                       Gemini writes the answer from them ◄┘
                                                                          │
                     citations verified, each sentence checked ─► answer + sources
```

- **Hybrid retrieval:** keyword search (PostgreSQL full-text search on the
  question's rare words) and meaning search (embeddings in pgvector) each rank
  the passages; reciprocal rank fusion combines the two rankings.
- **Reranking:** a cross-encoder reads the question with each of the 20 best
  passages and puts them in order; the best 6 go to the model.
- **Local where possible:** embeddings, reranking and OCR run on your machine.
  Only answering, fact and action extraction, and conflict checks call Gemini.

## Measured quality

Changes to retrieval and answering are measured on a fixed test set of
made-up documents (leases, policies, manuals, meeting notes), and kept only if
the score improves. Tests fail if a later change scores lower.

**Retrieval** (42 questions; is the answer page among the 6 passages the model reads?)

| | Answer page found | Answer page ranked first |
|---|---|---|
| Keyword then meaning search | 88% | 52% |
| + rank fusion and tokenizer fix | 94% | 69% |
| + local reranker | **100%** | **90%** |

**Answers** (36 questions answered by Gemini, scored by rules)

| | Result |
|---|---|
| Answers stating every expected fact | 30 of 30 |
| Facts backed by the passage the answer cites | 100% |
| Unanswerable questions declined | 6 of 6 |
| Median answer time | 2.9 s |

The test set is small and made up; it shows that each change helped, not that
answers are perfect on every real document.

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy, Alembic, Pydantic
- **Database:** PostgreSQL with pgvector and full-text search
- **AI:** `BAAI/bge-small-en-v1.5` embeddings and `ms-marco-MiniLM-L-6-v2`
  reranker (local, via fastembed), Tesseract OCR, Google Gemini (`google-genai`)
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, TanStack Query

## Getting started

### Prerequisites

- Python 3.11+
- PostgreSQL with the [pgvector](https://github.com/pgvector/pgvector) extension
- Node.js 22+
- Optional: [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) for
  scanned PDFs (on Windows: `winget install --id UB-Mannheim.TesseractOCR`).
  Without it, everything else works and scanned PDFs are marked as failed.
- Optional: a free [Gemini API key](https://aistudio.google.com) for questions,
  key facts, actions and conflict checks.

<details>
<summary>Installing pgvector on Windows</summary>

pgvector has no Windows installer. Build it once from an administrator
"x64 Native Tools Command Prompt for VS" (needs Visual Studio's "Desktop
development with C++"):

```bat
set "PGROOT=C:\Program Files\PostgreSQL\17"
git clone --branch v0.8.7 https://github.com/pgvector/pgvector.git
cd pgvector
nmake /F Makefile.win
nmake /F Makefile.win install
```
</details>

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Create a PostgreSQL database named `aletheia`, copy `.env.example` to `.env`
and set your database password (write `@` in it as `%40`). Then:

```bash
alembic upgrade head            # create the tables
uvicorn app.main:app --reload   # http://localhost:8000/api/v1/health
```

The embedding model (about 67 MB) and the reranker (about 80 MB) are
downloaded into `backend/models/` the first time they're needed, and run on
the CPU.

### Frontend

With the backend running:

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

Calls to `/api` are forwarded to the backend on port 8000.

## Configuration

Settings are read from `backend/.env` (see `.env.example`).

| Setting | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection (required) |
| `GEMINI_API_KEY` | Enables questions, key facts, actions and conflict checks |
| `LLM_MODEL`, `LLM_FALLBACK_MODEL` | The Gemini model, and the one tried when it's busy or over its limit |
| `COOKIE_SECURE` | Set to `true` when served over HTTPS |

When a usage limit is reached, the app says so and when to try again; search,
comparison and everything else keep working without a key.

## Privacy

Uploading, reading, searching and comparing documents never use an outside
service. Gemini receives:

- **Ask:** the question and the 6 passages chosen to answer it.
- **Key facts and Actions:** the whole document's text, only when you click them.
- **Check for conflicts:** up to 8 pairs of matched passages, only when you click it.

On Gemini's free tier, Google may use this data to improve its products: use
it with test documents only.

## Testing

```bash
cd backend
pytest                          # the full suite, in its own database (aletheia_test)
pytest tests/test_retrieval.py -s   # retrieval scores
pytest tests/test_answers.py -s     # answer scores
```

```bash
cd frontend
npm run lint
npm run build                   # type-checks, then builds
```

Tests never call Gemini. Answer quality is scored on answers recorded once
with `pytest tests/record_answers.py -s`, which does call Gemini and is run
only on purpose, for example after changing the prompt.

## Project structure

```
backend/
  app/
    api/         HTTP routes and access checks
    documents/   text extraction, OCR, chunking, embeddings, reranking
    qa/          Gemini client and answer checks
    services/    search, question answering, facts, actions, comparison
    models/      database tables
  alembic/       database migrations
  tests/         tests, test documents and the evaluation sets
frontend/
  src/
    api/         calls to the backend
    components/  the workspace page and its features
```

## Roadmap

- Rate limiting per user, and other security hardening
- Deployment and monitoring
- Evaluation of key facts, actions and conflict checks
