from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from backend.database import get_db
from backend.models import Patient, Record, Prescription

router = APIRouter(prefix="/api/patients", tags=["patients"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class PatientUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    contact: Optional[str] = None
    blood_type: Optional[str] = None
    allergies: Optional[list] = None


# ── Serializers ───────────────────────────────────────────────────────────────

def _record_to_dict(r: Record) -> dict:
    return {
        "id": r.id,
        "patient_id": r.patient_id,
        "transcript": r.transcript,
        "chief_complaint": r.chief_complaint,
        "symptoms": r.symptoms,
        "diagnoses": r.diagnoses,
        "prescriptions": [
            {
                "drug": rx.drug,
                "dose": rx.dose,
                "frequency": rx.frequency,
                "duration": rx.duration,
            }
            for rx in r.prescriptions
        ],
        "vitals": r.vitals,
        "notes": r.notes,
        "follow_up": r.follow_up,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _patient_to_dict(p: Patient, include_records: bool = False) -> dict:
    d = {
        "id": p.id,
        "name": p.name,
        "age": p.age,
        "gender": p.gender,
        "contact": p.contact,
        "blood_type": p.blood_type,
        "allergies": p.allergies,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
    if include_records:
        d["visits"] = [_record_to_dict(r) for r in p.records]  # keep "visits" key for frontend compat
    return d


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
def list_patients(q: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Patient)
    if q:
        query = query.filter(Patient.name.ilike(f"%{q}%"))
    patients = query.order_by(Patient.updated_at.desc()).all()
    return [_patient_to_dict(p) for p in patients]


@router.get("/{patient_id}")
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    p = db.query(Patient).filter(Patient.id == patient_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    return _patient_to_dict(p, include_records=True)


@router.patch("/{patient_id}")
def update_patient(patient_id: int, data: PatientUpdate, db: Session = Depends(get_db)):
    p = db.query(Patient).filter(Patient.id == patient_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return _patient_to_dict(p)


@router.delete("/{patient_id}")
def delete_patient(patient_id: int, db: Session = Depends(get_db)):
    p = db.query(Patient).filter(Patient.id == patient_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.patch("/{patient_id}/visits/{visit_id}")
def update_record(patient_id: int, visit_id: int, data: dict, db: Session = Depends(get_db)):
    r = db.query(Record).filter(Record.id == visit_id, Record.patient_id == patient_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Visit not found")

    allowed = {"chief_complaint", "symptoms", "diagnoses", "vitals", "notes", "follow_up"}
    for field, value in data.items():
        if field in allowed:
            setattr(r, field, value)

    # Prescriptions: replace all rows for this record
    if "prescriptions" in data:
        for rx in list(r.prescriptions):
            db.delete(rx)
        db.flush()
        for rx_data in (data["prescriptions"] or []):
            db.add(Prescription(
                record_id=r.id,
                drug=rx_data.get("drug", ""),
                dose=rx_data.get("dose", ""),
                frequency=rx_data.get("frequency", ""),
                duration=rx_data.get("duration", ""),
            ))

    db.commit()
    db.refresh(r)
    return _record_to_dict(r)
