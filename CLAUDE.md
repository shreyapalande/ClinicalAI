# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```powershell
# Activate venv (Windows)
.\venv\Scripts\Activate.ps1

# Run dev server (auto-reloads on file changes)
.\venv\Scripts\uvicorn main:app --reload --port 8000

# Install dependencies
.\venv\Scripts\pip install -r requirements.txt

# Interactive API docs
# http://127.0.0.1:8000/docs
```

## Environment

Copy `.env` and fill in real keys before first run:
```
GEMINI_API_KEY=
ASSEMBLYAI_API_KEY=
DATABASE_URL=sqlite:///./clinical.db
```

`DATABASE_URL` defaults to SQLite. Swap in a PostgreSQL URL (e.g. Railway) and remove the `connect_args` guard in [db/database.py](db/database.py) when migrating.

## Architecture

The app is a FastAPI backend that serves a Vanilla JS SPA from `static/`. There is no build step — the frontend is plain HTML/CSS/JS loaded directly.

**Request flow for a new record:**
1. Browser sends audio file or raw transcript to `POST /api/record/`
2. [routes/record.py](routes/record.py) saves the file, calls AssemblyAI (`services/transcribe.py`) for speech-to-text
3. The transcript is sent to Gemini Flash (`services/gemini.py → extract_record`) which returns a structured JSON with `patient` and `visit` keys
4. The route upserts a `Patient` row (matched by name, case-insensitive) and creates a `Visit` row
5. `build_visit_text` flattens visit fields into a prose string; `embed_text` generates a 768-dim vector via `text-embedding-004`; the vector is stored as a JSON array in `Visit.embedding`

**Semantic search flow:**
- `GET /api/search/?q=<query>` embeds the query, loads all visits with non-null embeddings, scores each via pure-Python cosine similarity in [services/search.py](services/search.py), and returns top-k sorted results
- This runs in-process and is fine for hundreds of records. At scale, replace with pgvector's `<=>` operator.

**Frontend routing:**
- [static/js/router.js](static/js/router.js) is a minimal hash-free router; `Router.go(page, id)` swaps content in `#app` by calling page render functions
- All API calls go through the thin fetch wrapper in [static/js/api.js](static/js/api.js)

## Key conventions

- **Google Gemini SDK**: use `from google import genai` (`google-genai` package). The old `google.generativeai` package is deprecated and will warn loudly — do not use it.
- **Database schema changes**: SQLAlchemy uses `Base.metadata.create_all` on startup (no migration tool). For schema changes, either drop and recreate the DB in dev, or add columns manually / via Alembic.
- **Embeddings**: stored as `JSON` (list of floats) in SQLite. The column comment in `models.py` marks the pgvector migration point — when switching to Postgres, change the column type to `Vector(768)` from `pgvector.sqlalchemy` and update `services/search.py` to use a DB-side query.
- **Patient deduplication**: the record routes match patients by `name ILIKE` — good enough for a demo, fragile in production.
- **Upload directory**: audio files land in `uploads/` at the project root (auto-created, gitignored).
