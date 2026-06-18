"""
CRUD tests for backend/routers/patients.py using FastAPI TestClient.
Runs against a throw-away in-memory SQLite DB — no files created.

Run from project root:
    .\\venv\\Scripts\\pytest backend/routers/test_patients.py -v
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ["DATABASE_URL"] = "sqlite://"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.models import Patient, Record, Prescription  # noqa: F401
from backend.routers.patients import router

# ── Test app + in-memory DB ───────────────────────────────────────────────────

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,   # all connections share the same in-memory DB
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
Base.metadata.create_all(bind=_engine)


def override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


# ── Fixture: insert a patient directly via the DB ────────────────────────────

@pytest.fixture()
def patient_id() -> int:
    """Insert a fresh patient and return its id. Cleaned up after the test."""
    db = _TestSession()
    p = Patient(name="Alice Nguyen", age=42, gender="Female", blood_type="O+", allergies=["Penicillin"])
    db.add(p)
    db.commit()
    pid = p.id
    db.close()
    yield pid
    # cleanup
    db = _TestSession()
    row = db.query(Patient).filter(Patient.id == pid).first()
    if row:
        db.delete(row)
        db.commit()
    db.close()


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_get_patient(patient_id):
    r = client.get(f"/api/patients/{patient_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == patient_id
    assert body["name"] == "Alice Nguyen"
    assert body["age"] == 42
    assert body["allergies"] == ["Penicillin"]
    assert "visits" in body
    assert isinstance(body["visits"], list)


def test_get_patient_not_found():
    r = client.get("/api/patients/99999")
    assert r.status_code == 404


def test_list_patients(patient_id):
    r = client.get("/api/patients/")
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()]
    assert patient_id in ids


def test_list_patients_search(patient_id):
    r = client.get("/api/patients/?q=Alice")
    assert r.status_code == 200
    results = r.json()
    assert any(p["id"] == patient_id for p in results)

    r2 = client.get("/api/patients/?q=ZZZNOMATCH")
    assert r2.status_code == 200
    assert r2.json() == []


def test_update_patient(patient_id):
    r = client.patch(f"/api/patients/{patient_id}", json={"age": 43, "blood_type": "A+"})
    assert r.status_code == 200
    body = r.json()
    assert body["age"] == 43
    assert body["blood_type"] == "A+"
    assert body["name"] == "Alice Nguyen"   # unchanged field preserved

    # Verify persisted
    r2 = client.get(f"/api/patients/{patient_id}")
    assert r2.json()["age"] == 43


def test_update_patient_not_found():
    r = client.patch("/api/patients/99999", json={"age": 50})
    assert r.status_code == 404


def test_delete_patient(patient_id):
    r = client.delete(f"/api/patients/{patient_id}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    r2 = client.get(f"/api/patients/{patient_id}")
    assert r2.status_code == 404


def test_delete_patient_not_found():
    r = client.delete("/api/patients/99999")
    assert r.status_code == 404
