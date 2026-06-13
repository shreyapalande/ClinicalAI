from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import Visit, Patient
from services.search import semantic_search

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/")
def search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(default=10, le=50),
    db: Session = Depends(get_db),
):
    visits = db.query(Visit).filter(Visit.embedding.isnot(None)).all()
    results = semantic_search(q, visits, top_k=top_k)

    out = []
    for visit, score in results:
        patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
        out.append({
            "score": round(score, 4),
            "visit_id": visit.id,
            "patient_id": visit.patient_id,
            "patient_name": patient.name if patient else "Unknown",
            "chief_complaint": visit.chief_complaint,
            "symptoms": visit.symptoms,
            "diagnoses": visit.diagnoses,
            "prescriptions": visit.prescriptions,
            "follow_up": visit.follow_up,
            "created_at": visit.created_at.isoformat() if visit.created_at else None,
        })
    return {"query": q, "results": out}
