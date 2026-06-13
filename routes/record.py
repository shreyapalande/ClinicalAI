import os
import shutil
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import Patient, Visit
from services.transcribe import transcribe_audio
from services.gemini import extract_record, embed_text, build_visit_text

router = APIRouter(prefix="/api/record", tags=["record"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/")
async def create_record(
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # save uploaded file
    ext = os.path.splitext(audio.filename)[1] or ".webm"
    save_path = os.path.join(UPLOAD_DIR, f"recording_{audio.filename}")
    with open(save_path, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    # transcribe
    try:
        transcript = transcribe_audio(save_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {e}")

    # extract structured data
    try:
        extracted = extract_record(transcript)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction error: {e}")

    patient_data = extracted.get("patient", {})
    visit_data = extracted.get("visit", {})

    # find or create patient by name
    patient = None
    if patient_data.get("name"):
        patient = db.query(Patient).filter(
            Patient.name.ilike(patient_data["name"])
        ).first()

    if not patient:
        patient = Patient(
            name=patient_data.get("name") or "Unknown",
            age=patient_data.get("age"),
            gender=patient_data.get("gender"),
            contact=patient_data.get("contact"),
            blood_type=patient_data.get("blood_type"),
            allergies=patient_data.get("allergies", []),
        )
        db.add(patient)
        db.flush()

    # build embedding
    visit_text = build_visit_text(visit_data)
    embedding = embed_text(visit_text) if visit_text else None

    visit = Visit(
        patient_id=patient.id,
        transcript=transcript,
        audio_filename=audio.filename,
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
    db.refresh(patient)
    db.refresh(visit)

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
    db: Session = Depends(get_db),
):
    try:
        extracted = extract_record(transcript)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction error: {e}")

    patient_data = extracted.get("patient", {})
    visit_data = extracted.get("visit", {})

    patient = None
    if patient_data.get("name"):
        patient = db.query(Patient).filter(
            Patient.name.ilike(patient_data["name"])
        ).first()

    if not patient:
        patient = Patient(
            name=patient_data.get("name") or "Unknown",
            age=patient_data.get("age"),
            gender=patient_data.get("gender"),
            contact=patient_data.get("contact"),
            blood_type=patient_data.get("blood_type"),
            allergies=patient_data.get("allergies", []),
        )
        db.add(patient)
        db.flush()

    visit_text = build_visit_text(visit_data)
    try:
        embedding = embed_text(visit_text) if visit_text else None
    except Exception as e:
        print(f"[embed] WARNING: {e}", flush=True)
        embedding = None

    visit = Visit(
        patient_id=patient.id,
        transcript=transcript,
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

    return {
        "patient_id": patient.id,
        "visit_id": visit.id,
        "patient_name": patient.name,
        "transcript": transcript,
        "extracted": extracted,
    }
