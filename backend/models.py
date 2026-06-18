from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, JSON, ForeignKey, UniqueConstraint,  # noqa: F401
)
from sqlalchemy.orm import relationship
from backend.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    age = Column(Integer)
    gender = Column(String)
    contact = Column(String)
    blood_type = Column(String)
    allergies = Column(JSON, default=list)       # ["Penicillin", "Sulfa"]
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    records = relationship(
        "Record",
        back_populates="patient",
        order_by="Record.created_at.desc()",
        cascade="all, delete-orphan",
    )


class Record(Base):
    """A single clinical encounter (formerly Visit)."""
    __tablename__ = "records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)

    transcript = Column(Text)
    audio_filename = Column(String)

    chief_complaint = Column(Text)
    symptoms = Column(JSON, default=list)        # ["headache", "fever"]
    diagnoses = Column(JSON, default=list)       # ["tension headache"]
    vitals = Column(JSON, default=dict)          # {bp, hr, temp, weight, height}
    notes = Column(Text)
    follow_up = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("Patient", back_populates="records")
    prescriptions = relationship(
        "Prescription",
        back_populates="record",
        cascade="all, delete-orphan",
    )
    # one-to-one: a record has at most one embedding row
    embedding = relationship(
        "Embedding",
        back_populates="record",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("records.id", ondelete="CASCADE"), nullable=False)

    drug = Column(String, nullable=False)
    dose = Column(String)
    frequency = Column(String)
    duration = Column(String)

    record = relationship("Record", back_populates="prescriptions")


class Embedding(Base):
    """Stores the semantic embedding for a Record. One row per Record.
    Migrate vector column to pgvector Vector(3072) when moving to Postgres.
    """
    __tablename__ = "embeddings"
    __table_args__ = (UniqueConstraint("record_id"),)

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, ForeignKey("records.id", ondelete="CASCADE"), nullable=False)

    # JSON-stringified float array stored as Text in SQLite.
    # Switch to: from pgvector.sqlalchemy import Vector; vector = Column(Vector(3072))
    vector = Column(Text, nullable=False)
    embed_model = Column(String, default="gemini-embedding-001")
    created_at = Column(DateTime, default=datetime.utcnow)

    record = relationship("Record", back_populates="embedding")
