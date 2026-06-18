import os
import shutil
from typing import Optional
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import Patient, Visit
from services.transcribe import transcribe_audio
from services.gemini import extract_record, embed_text, build_visit_text

router = APIRouter(prefix="/api/record", tags=["record"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _resolve_patient(patient_id: Optional[int], extracted_patient: dict, db: Session) -> Patient:
    """Return an existing patient by ID, or find/create one from extracted data."""
    if patient_id:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
        return patient

    # fallback: match by name or create new
    patient = None
    if extracted_patient.get("name"):
        patient = db.query(Patient).filter(
            Patient.name.ilike(extracted_patient["name"])
        ).first()

    if not patient:
        patient = Patient(
            name=extracted_patient.get("name") or "Unknown",
            age=extracted_patient.get("age"),
            gender=extracted_patient.get("gender"),
            contact=extracted_patient.get("contact"),
            blood_type=extracted_patient.get("blood_type"),
            allergies=extracted_patient.get("allergies", []),
        )
        db.add(patient)
        db.flush()

    return patient


def _save_visit(patient: Patient, visit_data: dict, transcript: str,
                audio_filename: Optional[str], db: Session) -> Visit:
    visit_text = build_visit_text(visit_data)
    try:
        embedding = embed_text(visit_text) if visit_text else None
    except Exception as e:
        print(f"[embed] WARNING: {e}", flush=True)
        embedding = None

    visit = Visit(
        patient_id=patient.id,
        transcript=transcript,
        audio_filename=audio_filename,
        chief_complaint=visit_data.get("chief_complaint"),
        symptoms=visit_data.get("symptoms", []),
        diagnoses=visit_data.get("diagnoses", []),
        prescriptions=visit_data.get("prescriptions", []),
        vitals=visit_data.get("vitals", {}),
        notes=visit_data.get("notes"),
        follow_up=visit_data.get("follow_up"),
        embedding=embedding,
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit


@router.post("/")
async def create_record(
    audio: UploadFile = File(...),
    patient_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    save_path = os.path.join(UPLOAD_DIR, f"recording_{audio.filename}")
    with open(save_path, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    try:
        transcript = transcribe_audio(save_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {e}")

    try:
        extracted = extract_record(transcript)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction error: {e}")

    patient = _resolve_patient(patient_id, extracted.get("patient", {}), db)
    visit = _save_visit(patient, extracted.get("visit", {}), transcript, audio.filename, db)

    return {
        "patient_id": patient.id,
        "visit_id": visit.id,
        "patient_name": patient.name,
        "transcript": transcript,
        "extracted": extracted,
    }


@router.post("/transcript")
async def record_from_transcript(
    transcript: str = Form(...),
    patient_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    try:
        extracted = extract_record(transcript)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction error: {e}")

    patient = _resolve_patient(patient_id, extracted.get("patient", {}), db)
    visit = _save_visit(patient, extracted.get("visit", {}), transcript, None, db)

    return {
        "patient_id": patient.id,
        "visit_id": visit.id,
        "patient_name": patient.name,
        "transcript": transcript,
        "extracted": extracted,
    }
