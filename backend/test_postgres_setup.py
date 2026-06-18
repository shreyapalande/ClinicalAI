"""
Postgres integration setup + smoke test.
Run from project root:
    .\\venv\\Scripts\\python backend/test_postgres_setup.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pg8000.native


def section(title):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")


def main():
    section("1. Ensure 'clinai' database exists")
    try:
        admin = pg8000.native.Connection(
            "postgres", password="postgres", host="localhost", port=5432, database="postgres"
        )
        rows = admin.run("SELECT datname FROM pg_database WHERE datname = :name", name="clinai")
        if not rows:
            admin.run("CREATE DATABASE clinai")
            print("  Created database 'clinai'")
        else:
            print("  Database 'clinai' already exists")
        admin.close()
    except Exception as e:
        print(f"  FAILED to connect to Postgres: {e}")
        sys.exit(1)

    section("2. init_db() — create all 4 tables via SQLAlchemy")
    os.environ["DATABASE_URL"] = "postgresql+pg8000://postgres:postgres@localhost:5432/clinai"
    from backend.database import init_db, engine
    try:
        init_db()
        print("  Tables created (or already exist).")
    except Exception as e:
        print(f"  FAILED: {e}")
        sys.exit(1)

    section("3. Verify tables exist in Postgres")
    from sqlalchemy import inspect
    insp = inspect(engine)
    tables = insp.get_table_names()
    expected = {"patients", "records", "prescriptions", "embeddings"}
    for t in sorted(expected):
        status = "✓" if t in tables else "✗ MISSING"
        print(f"  {status}  {t}")
    missing = expected - set(tables)
    if missing:
        print(f"\n  ERROR: missing tables: {missing}")
        sys.exit(1)

    section("4. Insert + read-back smoke test")
    from backend.database import SessionLocal
    from backend.models import Patient, Record, Prescription, Embedding
    import json

    db = SessionLocal()
    try:
        p = Patient(name="Smoke Test Patient", age=30, gender="Female", allergies=["None"])
        db.add(p)
        db.flush()

        r = Record(
            patient_id=p.id,
            chief_complaint="Smoke test complaint",
            symptoms=["test"],
            diagnoses=["none"],
            vitals={},
        )
        db.add(r)
        db.flush()

        db.add(Prescription(record_id=r.id, drug="Placebo", dose="1mg", frequency="daily", duration="1 day"))
        db.add(Embedding(record_id=r.id, vector=json.dumps([0.5] * 3072), embed_model="test"))
        db.commit()
        print(f"  Inserted patient id={p.id}, record id={r.id}")

        loaded = db.query(Patient).filter(Patient.id == p.id).first()
        assert loaded.name == "Smoke Test Patient"
        assert len(loaded.records) == 1
        rec = loaded.records[0]
        assert len(rec.prescriptions) == 1
        assert rec.embedding is not None
        import json as _json
        assert len(_json.loads(rec.embedding.vector)) == 3072
        print(f"  Read-back OK — patient, record, prescription, embedding all present")

        db.delete(loaded)
        db.commit()
        print(f"  Cleanup OK (cascade delete)")

    except Exception as e:
        db.rollback()
        print(f"  FAILED: {e}")
        raise
    finally:
        db.close()

    print(f"\n{'─'*55}")
    print("  Postgres setup verified.")
    print(f"{'─'*55}\n")


if __name__ == "__main__":
    main()
