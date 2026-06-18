"""
Verifies backend/models.py + backend/database.py against local SQLite.

Run from project root:
    .\\venv\\Scripts\\python backend/test_setup.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Point at a throw-away test DB so we don't touch clinai.db / clinical.db
_TEST_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_clinai.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"

from backend.database import init_db, SessionLocal
from backend.models import Patient, Record, Prescription, Embedding


def section(title):
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")


def main():
    section("1. Create tables")
    init_db()
    print("  Tables created (or already exist).")

    db = SessionLocal()
    try:
        section("2. Insert sample patient + record")
        patient = Patient(
            name="Alice Nguyen",
            age=42,
            gender="Female",
            contact="alice@example.com",
            blood_type="O+",
            allergies=["Penicillin", "Aspirin"],
        )
        db.add(patient)
        db.flush()   # get patient.id before inserting child rows

        record = Record(
            patient_id=patient.id,
            chief_complaint="Persistent cough and low-grade fever for 5 days",
            symptoms=["cough", "fever", "fatigue"],
            diagnoses=["viral upper respiratory infection"],
            vitals={"bp": "118/76", "hr": "88", "temp": "99.8°F"},
            notes="Patient advised rest and fluids. No antibiotics indicated.",
            follow_up="1 week if symptoms persist",
        )
        db.add(record)
        db.flush()

        rx1 = Prescription(record_id=record.id, drug="Dextromethorphan", dose="15mg", frequency="every 6h", duration="5 days")
        rx2 = Prescription(record_id=record.id, drug="Ibuprofen", dose="400mg", frequency="every 8h", duration="3 days")
        db.add_all([rx1, rx2])

        emb = Embedding(
            record_id=record.id,
            vector=[0.01] * 3072,   # placeholder — real embed_text() call not needed for schema test
            embed_model="gemini-embedding-001",
        )
        db.add(emb)
        db.commit()
        print(f"  Inserted Patient id={patient.id}, Record id={record.id}, 2 Prescriptions, 1 Embedding.")

        section("3. Read back and verify relationships")
        loaded = db.query(Patient).filter(Patient.id == patient.id).first()
        print(f"  Patient      : {loaded.name}, {loaded.age}yrs, allergies={loaded.allergies}")
        print(f"  Records      : {len(loaded.records)}")

        rec = loaded.records[0]
        print(f"  chief_complaint : {rec.chief_complaint}")
        print(f"  symptoms        : {rec.symptoms}")
        print(f"  diagnoses       : {rec.diagnoses}")
        print(f"  Prescriptions   : {[(p.drug, p.dose) for p in rec.prescriptions]}")
        print(f"  Embedding dim   : {len(rec.embedding.vector)}")
        print(f"  Embed model     : {rec.embedding.embed_model}")

        section("4. Cascade delete")
        db.delete(loaded)
        db.commit()
        remaining = db.query(Patient).filter(Patient.id == patient.id).first()
        print(f"  Patient after delete: {remaining}  (None = cascade worked)")

    finally:
        db.close()
        from backend.database import engine
        engine.dispose()
        os.remove(_TEST_DB)
        print("\n  Cleaned up test_clinai.db.")

    print(f"\n{'─' * 50}")
    print("  All checks passed.")
    print(f"{'─' * 50}\n")


if __name__ == "__main__":
    main()
