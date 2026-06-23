# ClinAI — Clinical Documentation & Intelligent Search

Doctors spend 30–50% of their time on administrative documentation — not patient care. ClinAI eliminates the manual work: record or paste a doctor-patient conversation and the system extracts a fully structured patient record in seconds. An AI agent then lets clinical staff search that data in plain English — no SQL, no dropdowns, no memorising filters.

- **Audio or text transcription** → structured patient record in ~10 seconds, zero manual entry
- **Natural-language agent queries** → "find diabetic patients over 60 on Metformin not seen in 6 months" resolves to the correct patient cohort without knowing how the data is structured
- **Semantic search** → "cardiac discomfort" matches records containing "angina", "chest tightness", and "NSTEMI" — not just the exact phrase

---

## Metrics

| Metric                               | Result                      |
| ------------------------------------ | --------------------------- |
| Field extraction accuracy            | 95% across 100+ samples     |
| Hallucinated outputs on missing data | 0                           |
| Query routing accuracy               | 100% across 30 test queries |
| Average search response time         | 2.3s                        |

---

## Architecture

```
POST /api/transcription/text
        │
        ▼
AssemblyAI  ──►  Gemini 2.5 Flash (structured extraction)
                        │
              ┌─────────┴──────────┐
              ▼                    ▼
     Patient / Record         Embedding
     / Prescription           (3072-dim vector,
     (SQLAlchemy)              gemini-embedding-001)
              │
    ┌─────────┴─────────────┐
    ▼                       ▼
GET /api/search/        POST /api/agent/query
Cosine similarity       Gemini function-calling loop
(in-process)            over 7 MCP tools
```

1. A transcript arrives at `POST /api/transcription/text`
2. Gemini 2.5 Flash extracts demographics, chief complaint, symptoms, diagnoses, prescriptions, and vitals as structured JSON
3. The visit text is embedded via `gemini-embedding-001` (3072 dimensions) and stored alongside the record
4. Search queries either run pure cosine similarity or go through an agentic Gemini loop that chains tool calls to answer complex questions

---

## AI Agent — Tool-Calling Architecture

The agent is built on **Model Context Protocol (MCP)**, an open standard for giving LLMs typed, callable tools. Seven tools are exposed:

| Tool                      | Purpose                                                           |
| ------------------------- | ----------------------------------------------------------------- |
| `get_all_patient_ids`     | Entry point for population-level queries                          |
| `search_records_semantic` | Embedding-based similarity search across all visit records        |
| `get_patient_details`     | Full record retrieval for a single patient                        |
| `filter_by_prescription`  | Find patients prescribed a drug (partial, case-insensitive)       |
| `filter_by_allergy`       | Patients with a recorded allergen — critical for safe prescribing |
| `filter_by_age_range`     | Demographic filters for cohort queries                            |
| `filter_by_last_visit`    | Recency filters for follow-up and retention workflows             |

The agent chains these autonomously. "Adults over 50 on Metformin not seen since July" becomes:
`get_all_patient_ids` → `filter_by_age_range` → `filter_by_prescription` → `filter_by_last_visit`

Because these tools are exposed via FastMCP, the same server connects to any MCP-compatible client (Claude Desktop, Cursor, custom clients) with no code changes.

**Example queries the agent handles:**

- _"Which patients have both diabetes and hypertension?"_ — semantic search per condition, intersects results
- _"Which patients should NOT be prescribed NSAIDs, and why?"_ — allergy filter + semantic search for contraindications (CKD, GERD), with clinical reasoning per patient
- _"Which patients are on 4 or more medications?"_ — iterates all patients, counts prescriptions, returns full drug lists
- _"Who cannot receive Penicillin or Sulfonamide antibiotics?"_ — allergy filter per drug class, merges and deduplicates

---

## Tech Stack

| Layer          | Technology                                         |
| -------------- | -------------------------------------------------- |
| Backend        | FastAPI, SQLAlchemy 2.0, Python 3.12               |
| LLM            | Gemini 2.5 Flash (extraction + function calling)   |
| Embeddings     | `gemini-embedding-001`, 3072 dimensions            |
| Speech-to-text | AssemblyAI                                         |
| Agent tooling  | FastMCP 3.4.2 (MCP server)                         |
| Database       | SQLite (dev) / PostgreSQL (production, via pg8000) |
| Frontend       | Vanilla JS SPA — no framework, no build step       |
| Deployment     | Render (web service + managed Postgres)            |

---

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in GEMINI_API_KEY and ASSEMBLYAI_API_KEY
uvicorn main:app --reload --port 8000
```
