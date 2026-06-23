import re
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query

from backend.database import SessionLocal
from backend.models import Patient, Record
from backend.tools import (
    filter_by_age_range,
    filter_by_allergy,
    filter_by_last_visit,
    filter_by_prescription,
    get_all_patient_ids,
    get_patient_details,
    search_records_semantic,
)

router = APIRouter(prefix="/api/search", tags=["search"])


# ── Routing classifiers ───────────────────────────────────────────────────────

_RE_ID = re.compile(
    r'\b(patient\s*#?\s*\d+|id\s*[:#]?\s*\d+|#\s*\d+)\b', re.IGNORECASE
)
_RE_NAME = re.compile(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$')
_RE_FIND_NAME = re.compile(
    r'\b(find|show|lookup|look up|get|fetch)\b\s+(?:patient\s+)?([A-Z][a-z]+ [A-Z][a-z]+)',
    re.IGNORECASE,
)
_RE_AGE = re.compile(
    r'\b(over|under|above|below|older than|younger than|aged?)\s+\d+'
    r'|\bbetween\s+\d+\s+and\s+\d+',
    re.IGNORECASE,
)
_RE_DRUG = re.compile(
    r'\b(on|taking|prescribed?|prescrib\w+|medication|drug)\b', re.IGNORECASE
)
_RE_ALLERGY = re.compile(
    r'\b(allergic to|allerg\w+|intolerant to)\b', re.IGNORECASE
)
_RE_DATE = re.compile(
    r'\b(last\s+\d+\s+(day|week|month|year)s?'
    r'|since\s+\d{4}|before\s+\d{4}'
    r'|not\s+seen|haven.t\s+(been|visited)|overdue)\b',
    re.IGNORECASE,
)


def _classify(q: str) -> str:
    s = q.strip()
    if _RE_ID.search(s) or _RE_NAME.match(s) or _RE_FIND_NAME.search(s):
        return "lookup"
    if _RE_AGE.search(s) or _RE_DRUG.search(s) or _RE_ALLERGY.search(s) or _RE_DATE.search(s):
        return "structured"
    return "semantic"


# ── Structured filter parser ──────────────────────────────────────────────────

def _parse_age_range(q: str) -> tuple[Optional[int], Optional[int]]:
    m = re.search(r'between\s+(\d+)\s+and\s+(\d+)', q, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'\b(over|above|older than|aged?\s+over)\s+(\d+)', q, re.IGNORECASE)
    if m:
        return int(m.group(2)), None
    m = re.search(r'\b(under|below|younger than|aged?\s+under)\s+(\d+)', q, re.IGNORECASE)
    if m:
        return None, int(m.group(2))
    return None, None


def _parse_drug(q: str) -> Optional[str]:
    m = re.search(
        r'\b(?:on|taking|prescribed?|prescrib\w+)\s+([A-Za-z]\w+)', q, re.IGNORECASE
    )
    return m.group(1) if m else None


def _parse_allergen(q: str) -> Optional[str]:
    m = re.search(r'\ballergic to\s+([A-Za-z]\w+)', q, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r'\baller\w+\s+(?:to\s+)?([A-Za-z]\w+)', q, re.IGNORECASE)
    return m.group(1) if m else None


def _parse_date_window(q: str) -> tuple[Optional[str], Optional[str]]:
    m = re.search(r'last\s+(\d+)\s+(day|week|month|year)s?', q, re.IGNORECASE)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        days = {"day": 1, "week": 7, "month": 30, "year": 365}[unit] * n
        cutoff = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
        return None, cutoff          # after_date = cutoff (seen since then)
    m = re.search(r'since\s+(\d{4})', q, re.IGNORECASE)
    if m:
        return None, f"{m.group(1)}-01-01"
    m = re.search(r'before\s+(\d{4})', q, re.IGNORECASE)
    if m:
        return f"{m.group(1)}-01-01", None
    if re.search(r'\b(not\s+seen|overdue|haven.t)\b', q, re.IGNORECASE):
        cutoff = (datetime.utcnow() - timedelta(days=180)).date().isoformat()
        return cutoff, None          # before_date = 6 months ago
    return None, None


def _handle_structured(q: str) -> list[dict]:
    db = SessionLocal()
    try:
        ids = get_all_patient_ids(db=db)

        min_age, max_age = _parse_age_range(q)
        if min_age is not None or max_age is not None:
            ids = filter_by_age_range(ids, min_age=min_age, max_age=max_age, db=db)

        drug = _parse_drug(q)
        if drug:
            ids = filter_by_prescription(ids, medication=drug, db=db)

        allergen = _parse_allergen(q)
        if allergen:
            ids = filter_by_allergy(ids, allergen=allergen, db=db)

        before, after = _parse_date_window(q)
        if before or after:
            ids = filter_by_last_visit(ids, before_date=before, after_date=after, db=db)

        patients = []
        for pid in ids:
            p = db.query(Patient).filter(Patient.id == pid).first()
            if not p:
                continue
            last = (
                db.query(Record)
                .filter(Record.patient_id == pid)
                .order_by(Record.created_at.desc())
                .first()
            )
            patients.append({
                "patient_id": p.id,
                "patient_name": p.name,
                "age": p.age,
                "gender": p.gender,
                "allergies": p.allergies or [],
                "latest_visit": last.created_at.isoformat() if last and last.created_at else None,
                "latest_diagnosis": (last.diagnoses or [None])[0] if last else None,
            })
        return patients
    finally:
        db.close()


# ── Lookup handler ────────────────────────────────────────────────────────────

def _extract_id(q: str) -> Optional[int]:
    m = _RE_ID.search(q)
    if m:
        return int(re.search(r'\d+', m.group()).group())
    return None


def _extract_name(q: str) -> Optional[str]:
    m = _RE_FIND_NAME.search(q)
    if m:
        return m.group(2)
    if _RE_NAME.match(q.strip()):
        return q.strip()
    return None


def _handle_lookup(q: str) -> list[dict]:
    db = SessionLocal()
    try:
        pid = _extract_id(q)
        if pid is not None:
            result = get_patient_details(pid, db=db)
            return [result] if "error" not in result else []

        name = _extract_name(q)
        if name:
            rows = (
                db.query(Patient)
                .filter(Patient.name.ilike(f"%{name}%"))
                .all()
            )
            return [
                {
                    "patient_id": p.id,
                    "patient_name": p.name,
                    "age": p.age,
                    "gender": p.gender,
                    "blood_type": p.blood_type,
                    "allergies": p.allergies or [],
                }
                for p in rows
            ]
        return []
    finally:
        db.close()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/")
def search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(default=10, le=50),
):
    results = search_records_semantic(q, top_k=top_k)
    return {"query": q, "results": results}


@router.post("/unified")
def unified_search(body: dict = Body(...)):
    q = (body.get("q") or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="q required")

    route = _classify(q)

    if route == "lookup":
        results = _handle_lookup(q)
    elif route == "structured":
        results = _handle_structured(q)
    else:
        results = [
            {**r, "score": r.get("score")}
            for r in search_records_semantic(q, top_k=body.get("top_k", 10))
        ]

    return {"route": route, "query": q, "results": results, "count": len(results)}
