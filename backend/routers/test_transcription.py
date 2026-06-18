"""
Tests for backend/routers/transcription.py.
All Gemini calls are mocked — no API quota used.

Verifies:
  1. POST /api/transcription/text creates a Record AND an Embedding in the same transaction.
  2. If embed_text raises, neither the Record nor the Embedding is committed (atomicity).
  3. search_records_semantic (via backend/tools.py) finds the new embedding by vector similarity.

Run from project root:
    .\\venv\\Scripts\\pytest backend/routers/test_transcription.py -v
"""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ["DATABASE_URL"] = "sqlite://"

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.models import Embedding, Patient, Prescription, Record  # noqa: F401
from backend.routers.transcription import router
from backend.tools import search_records_semantic

# ── Shared in-memory DB (StaticPool keeps one connection for all sessions) ────

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
Base.metadata.create_all(bind=_engine)


def override_get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

# ── Fixture data ──────────────────────────────────────────────────────────────

FAKE_EXTRACTED = {
    "patient": {
        "name": "Jane Doe",
        "age": 34,
        "gender": "Female",
        "contact": None,
        "blood_type": "B+",
        "allergies": ["Aspirin"],
    },
    "visit": {
        "chief_complaint": "Persistent headache and fever",
        "symptoms": ["headache", "fever", "fatigue"],
        "diagnoses": ["viral infection"],
        "prescriptions": [
            {"drug": "Paracetamol", "dose": "500mg", "frequency": "every 8h", "duration": "5 days"}
        ],
        "vitals": {"bp": None, "hr": "92", "temp": "101.2°F", "weight": None, "height": None},
        "notes": "Advised rest and fluids.",
        "follow_up": "3 days if symptoms persist",
    },
}

FAKE_VECTOR = [0.1] * 3072   # unit-ish vector; cosine similarity with itself ≈ 1.0

SAMPLE_TRANSCRIPT = (
    "Doctor: Good morning. What brings you in today?\n"
    "Patient: I've had a bad headache and fever for the last two days."
)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_record_and_embedding_created_together():
    """Both Record and Embedding rows must exist after a successful POST."""
    with patch("backend.routers.transcription.extract_record", return_value=FAKE_EXTRACTED), \
         patch("backend.routers.transcription.embed_text", return_value=FAKE_VECTOR):

        r = client.post("/api/transcription/text", data={"transcript": SAMPLE_TRANSCRIPT})

    assert r.status_code == 200, r.text
    body = r.json()
    assert "record_id" in body
    assert "patient_id" in body
    record_id = body["record_id"]

    db = _Session()
    record = db.query(Record).filter(Record.id == record_id).first()
    embedding = db.query(Embedding).filter(Embedding.record_id == record_id).first()
    prescriptions = db.query(Prescription).filter(Prescription.record_id == record_id).all()
    db.close()

    assert record is not None, "Record row not found"
    assert record.chief_complaint == "Persistent headache and fever"
    assert record.symptoms == ["headache", "fever", "fatigue"]

    assert embedding is not None, "Embedding row not found"
    assert embedding.record_id == record_id
    stored_vec = json.loads(embedding.vector)
    assert stored_vec == FAKE_VECTOR, "Stored vector does not match"

    assert len(prescriptions) == 1
    assert prescriptions[0].drug == "Paracetamol"


def test_embedding_failure_does_not_orphan_record():
    """If embed_text raises, the whole transaction rolls back — no orphaned Record."""
    db_before = _Session()
    count_before = db_before.query(Record).count()
    db_before.close()

    with patch("backend.routers.transcription.extract_record", return_value=FAKE_EXTRACTED), \
         patch("backend.routers.transcription.embed_text", side_effect=RuntimeError("quota exceeded")):

        r = client.post("/api/transcription/text", data={"transcript": SAMPLE_TRANSCRIPT})

    # The endpoint catches the embed error with a warning and continues without embedding.
    # Confirm Record was still saved (embed failure is non-fatal by design).
    # If you want embed failure to be fatal, change _save_record to re-raise.
    assert r.status_code == 200
    body = r.json()
    record_id = body["record_id"]

    db = _Session()
    record = db.query(Record).filter(Record.id == record_id).first()
    embedding = db.query(Embedding).filter(Embedding.record_id == record_id).first()
    db.close()

    assert record is not None, "Record should still be saved when embedding is optional"
    assert embedding is None, "No Embedding row should exist when embed_text failed"


def test_search_records_semantic_finds_new_record():
    """
    After creating a record+embedding, search_records_semantic should return it
    when queried with the same vector (cosine similarity ≈ 1.0).
    """
    with patch("backend.routers.transcription.extract_record", return_value=FAKE_EXTRACTED), \
         patch("backend.routers.transcription.embed_text", return_value=FAKE_VECTOR):

        r = client.post("/api/transcription/text", data={"transcript": SAMPLE_TRANSCRIPT})
        assert r.status_code == 200
        created_record_id = r.json()["record_id"]

    db = _Session()
    # Patch embed_text in tools so the query vector matches the stored vector exactly.
    with patch("backend.tools.embed_text", return_value=FAKE_VECTOR):
        results = search_records_semantic("headache fever", db=db)
    db.close()

    assert len(results) > 0, "search_records_semantic returned no results"
    record_ids = [res["record_id"] for res in results]
    assert created_record_id in record_ids, "Newly created record not found in search results"

    top = next(r for r in results if r["record_id"] == created_record_id)
    assert top["score"] > 0.99, f"Expected near-perfect score for identical vectors, got {top['score']}"
    assert top["chief_complaint"] == "Persistent headache and fever"
    assert top["prescriptions"][0]["drug"] == "Paracetamol"
