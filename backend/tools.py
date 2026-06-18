"""
Pure tool functions for the clinical search agent.
No FastMCP dependency — safe to import anywhere.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Optional

from db.database import SessionLocal
from db.models import Patient, Visit
from services.gemini import embed_text
from services.search import cosine_similarity


def _db():
    return SessionLocal()


def get_all_patient_ids() -> list[int]:
    """Returns the IDs of every patient in the database."""
    db = _db()
    try:
        return [p.id for p in db.query(Patient.id).all()]
    finally:
        db.close()


def search_records_semantic(query: str, top_k: int = 10) -> list[dict]:
    """Searches all visit records by semantic similarity. Returns up to top_k results."""
    db = _db()
    try:
        visits = db.query(Visit).filter(Visit.embedding.isnot(None)).all()
        if not visits:
            return []
        query_vec = embed_text(query)
        scored = [(v, cosine_similarity(query_vec, v.embedding)) for v in visits if v.embedding]
        scored.sort(key=lambda x: x[1], reverse=True)
        results = []
        for visit, score in scored[:top_k]:
            patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
            results.append({
                "patient_id": visit.patient_id,
                "patient_name": patient.name if patient else "Unknown",
                "visit_id": visit.id,
                "score": round(score, 4),
                "chief_complaint": visit.chief_complaint,
                "symptoms": visit.symptoms or [],
                "diagnoses": visit.diagnoses or [],
                "prescriptions": visit.prescriptions or [],
                "created_at": visit.created_at.isoformat() if visit.created_at else None,
            })
        return results
    finally:
        db.close()


def get_patient_details(patient_id: int) -> dict:
    """Returns the full medical record for a single patient."""
    db = _db()
    try:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            return {"error": f"Patient {patient_id} not found"}
        visits = (
            db.query(Visit)
            .filter(Visit.patient_id == patient_id)
            .order_by(Visit.created_at.desc())
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
            "visits": [
                {
                    "id": v.id,
                    "chief_complaint": v.chief_complaint,
                    "symptoms": v.symptoms or [],
                    "diagnoses": v.diagnoses or [],
                    "prescriptions": v.prescriptions or [],
                    "vitals": v.vitals or {},
                    "notes": v.notes,
                    "follow_up": v.follow_up,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                    "transcript": v.transcript,
                }
                for v in visits
            ],
        }
    finally:
        db.close()


def filter_by_last_visit(
    patient_ids: list[int],
    before_date: Optional[str] = None,
    after_date: Optional[str] = None,
) -> list[int]:
    """Filters patients by date of most recent visit."""
    db = _db()
    try:
        before = datetime.fromisoformat(before_date) if before_date else None
        after = datetime.fromisoformat(after_date) if after_date else None
        matched = []
        for pid in patient_ids:
            last = (
                db.query(Visit)
                .filter(Visit.patient_id == pid)
                .order_by(Visit.created_at.desc())
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
        db.close()


def filter_by_prescription(patient_ids: list[int], medication: str) -> list[int]:
    """Filters patients who have been prescribed a medication (partial, case-insensitive)."""
    db = _db()
    try:
        med = medication.lower()
        matched = []
        for pid in patient_ids:
            visits = db.query(Visit).filter(Visit.patient_id == pid).all()
            found = False
            for visit in visits:
                for rx in (visit.prescriptions or []):
                    drug = rx.get("drug", "") if isinstance(rx, dict) else str(rx)
                    if med in drug.lower():
                        found = True
                        break
                if found:
                    break
            if found:
                matched.append(pid)
        return matched
    finally:
        db.close()


def filter_by_age_range(
    patient_ids: list[int],
    min_age: Optional[int] = None,
    max_age: Optional[int] = None,
) -> list[int]:
    """Filters patients by age range."""
    db = _db()
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
        db.close()


def filter_by_allergy(patient_ids: list[int], allergen: str) -> list[int]:
    """Filters patients with a recorded allergy (partial, case-insensitive)."""
    db = _db()
    try:
        allergen_lower = allergen.lower()
        matched = []
        for pid in patient_ids:
            p = db.query(Patient).filter(Patient.id == pid).first()
            if not p:
                continue
            for a in (p.allergies or []):
                if allergen_lower in a.lower():
                    matched.append(pid)
                    break
        return matched
    finally:
        db.close()
