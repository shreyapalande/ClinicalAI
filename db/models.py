from sqlalchemy import Column, Integer, String, Text, DateTime, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from db.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    age = Column(Integer)
    gender = Column(String)
    contact = Column(String)
    blood_type = Column(String)
    allergies = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    visits = relationship("Visit", back_populates="patient", order_by="Visit.created_at.desc()", cascade="all, delete-orphan")


class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)

    # raw data
    transcript = Column(Text)
    audio_filename = Column(String)

    # extracted structured data
    chief_complaint = Column(Text)
    symptoms = Column(JSON, default=list)
    diagnoses = Column(JSON, default=list)
    prescriptions = Column(JSON, default=list)  # [{drug, dose, frequency, duration}]
    vitals = Column(JSON, default=dict)          # {bp, hr, temp, weight, height}
    notes = Column(Text)
    follow_up = Column(String)

    # embedding stored as JSON array (migrate to pgvector later)
    embedding = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("Patient", back_populates="visits")
