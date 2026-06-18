from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from db.database import get_db
from db.models import Patient, Visit

router = APIRouter(prefix="/api/patients", tags=["patients"])


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    contact: Optional[str] = None
    blood_type: Optional[str] = None
    allergies: Optional[list] = None


def visit_to_dict(v: Visit) -> dict:
    return {
        "id": v.id,
        "patient_id": v.patient_id,
        "transcript": v.transcript,
        "chief_complaint": v.chief_complaint,
        "symptoms": v.symptoms,
        "diagnoses": v.diagnoses,
        "prescriptions": v.prescriptions,
        "vitals": v.vitals,
        "notes": v.notes,
        "follow_up": v.follow_up,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def patient_to_dict(p: Patient, include_visits: bool = False) -> dict:
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
    if include_visits:
        d["visits"] = [visit_to_dict(v) for v in p.visits]
    return d


@router.get("/")
def list_patients(q: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Patient)
    if q:
        query = query.filter(Patient.name.ilike(f"%{q}%"))
    patients = query.order_by(Patient.updated_at.desc()).all()
    return [patient_to_dict(p) for p in patients]


@router.get("/{patient_id}")
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    p = db.query(Patient).filter(Patient.id == patient_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient_to_dict(p, include_visits=True)


@router.patch("/{patient_id}")
def update_patient(patient_id: int, data: PatientUpdate, db: Session = Depends(get_db)):
    p = db.query(Patient).filter(Patient.id == patient_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return patient_to_dict(p)


@router.delete("/{patient_id}")
def delete_patient(patient_id: int, db: Session = Depends(get_db)):
    p = db.query(Patient).filter(Patient.id == patient_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.patch("/{patient_id}/visits/{visit_id}")
def update_visit(patient_id: int, visit_id: int, data: dict, db: Session = Depends(get_db)):
    v = db.query(Visit).filter(Visit.id == visit_id, Visit.patient_id == patient_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Visit not found")
    allowed = {"chief_complaint", "symptoms", "diagnoses", "prescriptions", "vitals", "notes", "follow_up"}
    for field, value in data.items():
        if field in allowed:
            setattr(v, field, value)
    db.commit()
    db.refresh(v)
    return visit_to_dict(v)
