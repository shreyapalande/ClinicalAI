import json
import os
import shutil
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Embedding, Patient, Prescription, Record
from services.gemini import EMBED_MODEL, build_visit_text, embed_text, extract_record

router = APIRouter(prefix="/api/transcription", tags=["transcription"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _resolve_patient(patient_id: Optional[int], extracted_patient: dict, db: Session) -> Patient:
    if patient_id:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
        return patient

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


def _save_record(
    patient: Patient,
    record_data: dict,
    transcript: str,
    audio_filename: Optional[str],
    db: Session,
) -> Record:
    # Generate embedding before any DB write — failure here aborts the whole operation.
    record_text = build_visit_text(record_data)
    vector: Optional[list[float]] = None
    if record_text:
        try:
            vector = embed_text(record_text)
        except Exception as exc:
            print(f"[embed] WARNING: {exc}", flush=True)

    record = Record(
        patient_id=patient.id,
        transcript=transcript,
        audio_filename=audio_filename,
        chief_complaint=record_data.get("chief_complaint"),
        symptoms=record_data.get("symptoms", []),
        diagnoses=record_data.get("diagnoses", []),
        vitals=record_data.get("vitals", {}),
        notes=record_data.get("notes"),
        follow_up=record_data.get("follow_up"),
    )
    db.add(record)
    db.flush()  # assigns record.id without committing

    for rx in record_data.get("prescriptions", []):
        db.add(Prescription(
            record_id=record.id,
            drug=rx.get("drug", ""),
            dose=rx.get("dose", ""),
            frequency=rx.get("frequency", ""),
            duration=rx.get("duration", ""),
        ))

    if vector is not None:
        db.add(Embedding(
            record_id=record.id,
            vector=json.dumps(vector),  # Text column — JSON-stringified float array
            embed_model=EMBED_MODEL,
        ))

    db.commit()  # single commit: record + prescriptions + embedding all or nothing
    db.refresh(record)
    return record


@router.post("/text")
async def record_from_transcript(
    transcript: str = Form(...),
    patient_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    try:
        extracted = extract_record(transcript)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Extraction error: {exc}")

    patient = _resolve_patient(patient_id, extracted.get("patient", {}), db)
    record = _save_record(patient, extracted.get("visit", {}), transcript, None, db)

    return {
        "patient_id": patient.id,
        "record_id": record.id,
        "patient_name": patient.name,
        "transcript": transcript,
        "extracted": extracted,
    }


@router.post("/audio")
async def record_from_audio(
    audio: UploadFile = File(...),
    patient_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    from services.transcribe import transcribe_audio

    save_path = os.path.join(UPLOAD_DIR, f"recording_{audio.filename}")
    with open(save_path, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    try:
        transcript = transcribe_audio(save_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription error: {exc}")

    try:
        extracted = extract_record(transcript)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Extraction error: {exc}")

    patient = _resolve_patient(patient_id, extracted.get("patient", {}), db)
    record = _save_record(patient, extracted.get("visit", {}), transcript, audio.filename, db)

    return {
        "patient_id": patient.id,
        "record_id": record.id,
        "patient_name": patient.name,
        "transcript": transcript,
        "extracted": extracted,
    }
