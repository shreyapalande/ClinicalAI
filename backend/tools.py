"""
Pure tool functions for the clinical search agent.
No FastMCP dependency — safe to import anywhere.
Uses backend.database (new SQLAlchemy setup) and backend.models.
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import Embedding, Patient, Prescription, Record
from services.gemini import embed_text
from services.search import cosine_similarity


def _open_db() -> Session:
    return SessionLocal()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rx_list(record: Record) -> list[dict]:
    return [
        {"drug": rx.drug, "dose": rx.dose, "frequency": rx.frequency, "duration": rx.duration}
        for rx in record.prescriptions
    ]


# ── Tools ─────────────────────────────────────────────────────────────────────

def get_all_patient_ids(db: Optional[Session] = None) -> list[int]:
    """Returns the IDs of every patient in the database."""
    own = db is None
    db = db or _open_db()
    try:
        return [p.id for p in db.query(Patient.id).all()]
    finally:
        if own:
            db.close()


def search_records_semantic(
    query: str,
    top_k: int = 10,
    db: Optional[Session] = None,
) -> list[dict]:
    """
    Searches all records with embeddings by semantic similarity.
    Uses an ORM inner join of Record ↔ Embedding, then cosine similarity in Python.
    """
    own = db is None
    db = db or _open_db()
    try:
        rows = (
            db.query(Record, Embedding)
            .join(Embedding, Embedding.record_id == Record.id)
            .all()
        )
        if not rows:
            return []

        query_vec = embed_text(query)

        scored: list[tuple[Record, Embedding, float]] = []
        for record, emb in rows:
            vec = json.loads(emb.vector)
            score = cosine_similarity(query_vec, vec)
            scored.append((record, emb, score))

        scored.sort(key=lambda x: x[2], reverse=True)

        # Deduplicate: keep only the highest-scoring record per patient
        seen_patients: set[int] = set()
        results = []
        for record, _emb, score in scored:
            if record.patient_id in seen_patients:
                continue
            seen_patients.add(record.patient_id)
            patient = db.query(Patient).filter(Patient.id == record.patient_id).first()
            results.append({
                "patient_id": record.patient_id,
                "patient_name": patient.name if patient else "Unknown",
                "record_id": record.id,
                "score": round(score, 4),
                "chief_complaint": record.chief_complaint,
                "symptoms": record.symptoms or [],
                "diagnoses": record.diagnoses or [],
                "prescriptions": _rx_list(record),
                "created_at": record.created_at.isoformat() if record.created_at else None,
            })
            if len(results) >= top_k:
                break
        return results
    finally:
        if own:
            db.close()


def get_patient_details(patient_id: int, db: Optional[Session] = None) -> dict:
    """Returns the full medical record for a single patient."""
    own = db is None
    db = db or _open_db()
    try:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            return {"error": f"Patient {patient_id} not found"}

        records = (
            db.query(Record)
            .filter(Record.patient_id == patient_id)
            .order_by(Record.created_at.desc())
            .all()
        )
        return {
            "id": patient.id,
            "name": patient.name,
            "age": patient.age,
            "gender": patient.gender,
            "contact": patient.contact,
            "blood_type": patient.blood_type,
            "allergies": patient.allergies or [],
            "records": [
                {
                    "id": r.id,
                    "chief_complaint": r.chief_complaint,
                    "symptoms": r.symptoms or [],
                    "diagnoses": r.diagnoses or [],
                    "prescriptions": _rx_list(r),
                    "vitals": r.vitals or {},
                    "notes": r.notes,
                    "follow_up": r.follow_up,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "transcript": r.transcript,
                }
                for r in records
            ],
        }
    finally:
        if own:
            db.close()


def filter_by_last_visit(
    patient_ids: list[int],
    before_date: Optional[str] = None,
    after_date: Optional[str] = None,
    db: Optional[Session] = None,
) -> list[int]:
    """Filters patients by date of most recent record."""
    own = db is None
    db = db or _open_db()
    try:
        before = datetime.fromisoformat(before_date) if before_date else None
        after = datetime.fromisoformat(after_date) if after_date else None
        matched = []
        for pid in patient_ids:
            last = (
                db.query(Record)
                .filter(Record.patient_id == pid)
                .order_by(Record.created_at.desc())
                .first()
            )
            if not last:
                continue
            lv = last.created_at
            if before and lv >= before:
                continue
            if after and lv <= after:
                continue
            matched.append(pid)
        return matched
    finally:
        if own:
            db.close()


def filter_by_prescription(
    patient_ids: list[int],
    medication: str,
    db: Optional[Session] = None,
) -> list[int]:
    """Filters patients prescribed a medication (partial, case-insensitive drug name match)."""
    own = db is None
    db = db or _open_db()
    try:
        med = medication.lower()
        matched = []
        for pid in patient_ids:
            hit = (
                db.query(Prescription)
                .join(Record, Record.id == Prescription.record_id)
                .filter(Record.patient_id == pid)
                .all()
            )
            if any(med in rx.drug.lower() for rx in hit):
                matched.append(pid)
        return matched
    finally:
        if own:
            db.close()


def filter_by_age_range(
    patient_ids: list[int],
    min_age: Optional[int] = None,
    max_age: Optional[int] = None,
    db: Optional[Session] = None,
) -> list[int]:
    """Filters patients by age range."""
    own = db is None
    db = db or _open_db()
    try:
        matched = []
        for pid in patient_ids:
            p = db.query(Patient).filter(Patient.id == pid).first()
            if not p or p.age is None:
                continue
            if min_age is not None and p.age < min_age:
                continue
            if max_age is not None and p.age > max_age:
                continue
            matched.append(pid)
        return matched
    finally:
        if own:
            db.close()


def filter_by_allergy(
    patient_ids: list[int],
    allergen: str,
    db: Optional[Session] = None,
) -> list[int]:
    """Filters patients with a recorded allergy (partial, case-insensitive)."""
    own = db is None
    db = db or _open_db()
    try:
        allergen_lower = allergen.lower()
        matched = []
        for pid in patient_ids:
            p = db.query(Patient).filter(Patient.id == pid).first()
            if not p:
                continue
            if any(allergen_lower in a.lower() for a in (p.allergies or [])):
                matched.append(pid)
        return matched
    finally:
        if own:
            db.close()
