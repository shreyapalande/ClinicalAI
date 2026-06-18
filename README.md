# ClinAI — AI-Powered Clinical Documentation & Search

> A full-stack application that eliminates manual documentation from a doctor's workflow — recording a consultation and producing a structured patient record in under 10 seconds, with a natural-language search agent that answers questions like _"which elderly patients with hypertension were prescribed beta-blockers in the last month?"_

---

## The Problem

Physicians spend an average of **2 hours per day** on electronic health record (EHR) documentation — nearly 40% of their time at work. That's time not spent with patients. Beyond the burden, manual data entry introduces transcription errors into records that inform future prescribing decisions.

ClinAI addresses both problems: it automates the transcription-to-record pipeline and makes the resulting records queryable through a conversational AI agent.

---

## What It Does

**Record a consultation → structured record in one step**

A doctor uploads an audio file or pastes a raw transcript. The system:

1. Transcribes audio to text via AssemblyAI
2. Sends the transcript to Gemini 2.5 Flash with a structured extraction prompt
3. Returns a normalized record — chief complaint, symptoms, diagnoses, prescriptions with dosing, vitals, follow-up instructions — and upserts it to the patient's profile
4. Generates a 3072-dimensional semantic embedding and stores it alongside the record

**Query the database in plain English**

Two search modes:

- **Semantic Search** — embedding-based cosine similarity. "Chest pain" returns records containing "angina", "cardiac discomfort", "myocardial ischemia" — the model understands meaning, not just keywords.
- **AI Agent** — a Gemini function-calling loop over 7 composable MCP tools. Ask complex, multi-criteria questions and receive a structured prose answer with matched patient cards.

---

## MCP Architecture

The agent's intelligence is built on **Model Context Protocol (MCP)** — an open standard for exposing tool APIs to LLMs. The clinical database is surfaced as a FastMCP server with 7 typed tools:

| Tool                      | Purpose                                                                |
| ------------------------- | ---------------------------------------------------------------------- |
| `get_all_patient_ids`     | Entry point for population-level queries                               |
| `search_records_semantic` | Embedding-based similarity search across all visits                    |
| `get_patient_details`     | Full record retrieval for a single patient                             |
| `filter_by_prescription`  | Find patients prescribed a drug (partial, case-insensitive)            |
| `filter_by_allergy`       | Flag patients with a recorded allergen — critical for safe prescribing |
| `filter_by_age_range`     | Demographic filters for cohort queries                                 |
| `filter_by_last_visit`    | Recency filters for follow-up and retention workflows                  |

The agent chains these tools autonomously — a query like _"adults over 50 prescribed Metformin who haven't been seen since July"_ becomes a three-step function-calling loop: `get_all_patient_ids` → `filter_by_age_range` → `filter_by_prescription` → `filter_by_last_visit`.

Because these tools are exposed via **FastMCP**, the same server can connect to any MCP-compatible client — no code changes required.

```
┌─────────────────────────────────────────────────────────────────┐
│                          ClinAI Backend                         │
│                                                                 │
│   POST /api/transcription/text                                  │
│        │                                                        │
│        ▼                                                        │
│   AssemblyAI (audio) ──► Gemini 2.5 Flash (extraction)         │
│        │                         │                              │
│        ▼                         ▼                              │
│   Patient / Record / Prescription rows   +  Embedding row       │
│            (SQLAlchemy, single transaction)                      │
│                                                                 │
│   GET /api/search/            POST /api/agent/query             │
│        │                            │                           │
│        ▼                            ▼                           │
│   Cosine similarity         Gemini function-calling loop        │
│   (in-process, Python)      over FastMCP tool set               │
│                                                                 │
│   backend/mcp_server.py  ──►  Claude Desktop / Cursor / MCP    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Business Impact

| Metric                                     | Before                           | After                                      |
| ------------------------------------------ | -------------------------------- | ------------------------------------------ |
| Time to create a structured patient record | 5–10 min (manual EHR entry)      | ~10 seconds (automated)                    |
| Query method for patient cohorts           | Manual chart review or SQL       | Natural-language agent query               |
| Search recall for clinical synonyms        | 0% (keyword-only)                | High (semantic embedding)                  |
| Risk of transcription errors               | Present at every data-entry step | Eliminated from the documentation pipeline |
| EHR portability                            | Locked to schema                 | JSON-structured, schema-controlled         |

For a 10-doctor practice seeing 30 patients each per day: recovering even 30 minutes of documentation time per doctor per day is **5 hours of clinical time returned to patient care, daily.**

The allergy filtering tool directly addresses patient safety — knowing which patients are allergic to a class of drugs before prescribing is a workflow step that currently depends on the doctor remembering or the patient disclosing.

---

## Tech Stack

| Layer          | Technology                                       |
| -------------- | ------------------------------------------------ |
| Backend        | FastAPI, SQLAlchemy 2.0, Python 3.14             |
| LLM            | Gemini 2.5 Flash (extraction + function calling) |
| Embeddings     | `gemini-embedding-001`, 3072 dimensions          |
| Speech-to-text | AssemblyAI                                       |
| MCP server     | FastMCP 3.4.2                                    |
| Database       | SQLite (local dev) / PostgreSQL (production)     |
| Frontend       | Vanilla JS SPA, hash-free router, no build step  |

The SQLite → Postgres migration requires only a `DATABASE_URL` swap — the ORM layer and all tool functions are database-agnostic. The embedding column is marked for migration to `pgvector Vector(3072)` when scaling beyond in-process cosine similarity.

---

## Data Model

Four normalized tables with cascade deletes:

```
Patient
  └── Record (many per patient)
        ├── Prescription (many per record)
        └── Embedding    (one per record, 3072-dim vector stored as JSON text)
```

Patient deduplication is name-based (`ILIKE`) — existing patients matched on follow-up visits, new patients created automatically.

---

## Setup

```bash
# Clone and create virtualenv
python -m venv venv
.\venv\Scripts\Activate.ps1       # Windows
source venv/bin/activate           # macOS / Linux

pip install -r requirements.txt

# Copy and fill in .env
cp .env.example .env
# GEMINI_API_KEY=
# ASSEMBLYAI_API_KEY=
# DATABASE_URL=sqlite:///clinai.db

# Run
uvicorn main:app --reload --port 8000
# → http://localhost:8000
```

For PostgreSQL: set `DATABASE_URL=postgresql+pg8000://user:pass@host:5432/clinai`. No other changes required.

---

## Testing

```bash
# Unit tests (in-memory SQLite, all Gemini calls mocked)
pytest backend/routers/ -v

# Postgres integration test (requires Docker)
docker run -d --name clinai-postgres \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres \
  -p 5432:5432 postgres:16-alpine

python backend/test_postgres_integration.py
```

The integration test submits 6 real clinical transcripts, verifies all records and embeddings in Postgres, runs all 7 MCP tool queries, and tests follow-up visit deduplication.

---

## Project Structure

```
├── main.py                     # FastAPI app entry point
├── backend/
│   ├── database.py             # SQLAlchemy engine, session, init_db
│   ├── models.py               # ORM models: Patient, Record, Prescription, Embedding
│   ├── tools.py                # 7 MCP tool functions (no FastMCP dependency)
│   ├── mcp_server.py           # FastMCP wrapper — exposes tools to MCP clients
│   └── routers/
│       ├── transcription.py    # POST /api/transcription/text|audio
│       └── patients.py         # CRUD endpoints for patient records
├── routes/
│   ├── agent.py                # POST /api/agent/query — Gemini function-calling loop
│   └── search.py               # GET /api/search/ — cosine similarity search
├── services/
│   ├── gemini.py               # extract_record, embed_text, build_visit_text
│   ├── transcribe.py           # AssemblyAI wrapper
│   └── search.py               # cosine_similarity (pure Python)
└── static/                     # Vanilla JS SPA
    └── js/pages/
        ├── search.js           # Semantic + AI Agent tab UI
        └── patient.js          # Patient detail view
```
