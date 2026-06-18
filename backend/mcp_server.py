"""
Clinical AI MCP Server
Exposes patient record tools for an LLM search agent.
All tools read from the shared SQLite database via SQLAlchemy.

Typical agent workflow:
  1. get_all_patient_ids()             -> full population
  2. filter_by_*(patient_ids, ...)     -> narrow the list
  3. get_patient_details(patient_id)   -> fetch full record
  OR
  1. search_records_semantic(query)    -> find relevant visits directly
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Optional

from fastmcp import FastMCP
from db.database import SessionLocal
from db.models import Patient, Visit
from services.gemini import embed_text
from services.search import cosine_similarity

mcp = FastMCP("Clinical AI Search Agent")


def _db():
    return SessionLocal()


# ── CORE TOOLS ───────────────────────────────────────────────────────────────

@mcp.tool()
def get_all_patient_ids() -> list[int]:
    """
    Returns the IDs of every patient in the database.

    Use this as the entry point for population-wide queries.
    Pass the returned list into filter_by_* tools to narrow down to
    patients matching specific criteria.

    Returns:
        List of integer patient IDs.
    """
    db = _db()
    try:
        return [p.id for p in db.query(Patient.id).all()]
    finally:
        db.close()


@mcp.tool()
def search_records_semantic(query: str, top_k: int = 10) -> list[dict]:
    """
    Searches all patient visit records using semantic (meaning-based) similarity.

    Unlike keyword search, this understands intent — searching 'chest pain'
    will also match records containing 'angina', 'cardiac discomfort', or
    'myocardial ischemia'. Useful for open-ended clinical queries.

    Examples of good queries:
      - 'patients with breathing difficulties'
      - 'antibiotics prescribed for infection'
      - 'hypertension and high blood pressure'
      - 'anxiety or depression mental health'

    Args:
        query:  Natural-language description of what to find.
        top_k:  Maximum number of results to return (default 10).

    Returns:
        List of dicts sorted by descending relevance, each containing:
        patient_id, patient_name, visit_id, score (0-1), chief_complaint,
        symptoms, diagnoses, prescriptions, created_at.
    """
    db = _db()
    try:
        visits = db.query(Visit).filter(Visit.embedding.isnot(None)).all()
        if not visits:
            return []

        query_vec = embed_text(query)
        scored = [
            (v, cosine_similarity(query_vec, v.embedding))
            for v in visits if v.embedding
        ]
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


@mcp.tool()
def get_patient_details(patient_id: int) -> dict:
    """
    Returns the complete medical record for a single patient.

    Call this after identifying a patient of interest — via semantic search
    or filter tools — to retrieve full demographics and visit history before
    summarising or answering a clinical question about them.

    Args:
        patient_id: The numeric patient ID.

    Returns:
        Dict with demographics (name, age, gender, contact, blood_type,
        allergies) and a 'visits' list (newest first), each visit containing:
        chief_complaint, symptoms, diagnoses, prescriptions, vitals,
        notes, follow_up, created_at, transcript.
        Returns {"error": "..."} if the patient is not found.
    """
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


# ── FILTER TOOLS ─────────────────────────────────────────────────────────────

@mcp.tool()
def filter_by_last_visit(
    patient_ids: list[int],
    before_date: Optional[str] = None,
    after_date: Optional[str] = None,
) -> list[int]:
    """
    Filters patients by the date of their most recent visit.

    Use this to answer time-based questions such as:
      - 'patients who haven't been seen in the last 3 months' (before_date)
      - 'patients seen after January 2025' (after_date)
      - 'patients visited between two dates' (both params)

    Dates must be ISO format: YYYY-MM-DD (e.g. '2025-06-01').
    Patients with no recorded visits are excluded.

    Args:
        patient_ids:  List of patient IDs to filter (from get_all_patient_ids
                      or a previous filter).
        before_date:  Retain patients whose last visit was BEFORE this date.
        after_date:   Retain patients whose last visit was AFTER this date.

    Returns:
        Subset of patient_ids satisfying the date constraint.
    """
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


@mcp.tool()
def filter_by_prescription(
    patient_ids: list[int],
    medication: str,
) -> list[int]:
    """
    Filters patients who have ever been prescribed a specific medication.

    Matching is case-insensitive and partial — 'amox' matches 'Amoxicillin'.
    Searches across all visits for each patient.

    Use this to answer:
      - 'patients currently on metformin'
      - 'everyone prescribed a beta-blocker'
      - 'patients who have taken penicillin'

    Args:
        patient_ids:  List of patient IDs to filter.
        medication:   Drug name or partial name to search for.

    Returns:
        Subset of patient_ids who have been prescribed the medication.
    """
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


@mcp.tool()
def filter_by_age_range(
    patient_ids: list[int],
    min_age: Optional[int] = None,
    max_age: Optional[int] = None,
) -> list[int]:
    """
    Filters patients by age.

    Use this to answer demographic questions such as:
      - 'elderly patients over 65'
      - 'paediatric patients under 12'
      - 'adults between 40 and 60'

    Patients with no recorded age are excluded from results.

    Args:
        patient_ids:  List of patient IDs to filter.
        min_age:      Minimum age inclusive. Pass None for no lower bound.
        max_age:      Maximum age inclusive. Pass None for no upper bound.

    Returns:
        Subset of patient_ids whose age falls within the specified range.
    """
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


@mcp.tool()
def filter_by_allergy(
    patient_ids: list[int],
    allergen: str,
) -> list[int]:
    """
    Filters patients who have a recorded allergy to a specific substance.

    Matching is case-insensitive and partial — 'sulfa' matches 'Sulfamethoxazole'.
    Critical for safe prescribing workflows.

    Use this to answer:
      - 'patients allergic to penicillin' (before prescribing)
      - 'anyone with an NSAID allergy'
      - 'patients with latex sensitivity'

    Args:
        patient_ids:  List of patient IDs to filter.
        allergen:     Allergen name or partial name.

    Returns:
        Subset of patient_ids who have the allergen recorded.
    """
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


if __name__ == "__main__":
    mcp.run()
