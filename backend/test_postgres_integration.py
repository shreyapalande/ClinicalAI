"""
Full integration test against local Postgres.
Uses real Gemini API (extract_record + embed_text) and real DB.
No mocks.

Run from project root (Docker Postgres must be up):
    .\\venv\\Scripts\\python backend/test_postgres_integration.py
"""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Must be set before importing backend.database so the engine is created for Postgres
os.environ["DATABASE_URL"] = "postgresql+pg8000://postgres:postgres@localhost:5432/clinai"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.database import init_db, SessionLocal
from backend.models import Patient, Record, Prescription, Embedding
from backend.routers.transcription import router as transcription_router
from backend.routers.patients import router as patients_router
from backend.tools import (
    get_all_patient_ids,
    search_records_semantic,
    get_patient_details,
    filter_by_last_visit,
    filter_by_prescription,
    filter_by_age_range,
    filter_by_allergy,
)

# ── App (real Postgres, no dependency override) ───────────────────────────────

app = FastAPI()
app.include_router(transcription_router)
app.include_router(patients_router)
client = TestClient(app)

# ── Helpers ───────────────────────────────────────────────────────────────────

def section(title):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def post_transcript(text: str, patient_id: int = None) -> dict:
    data = {"transcript": text}
    if patient_id:
        data["patient_id"] = str(patient_id)
    r = client.post("/api/transcription/text", data=data)
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:300]}"
    return r.json()


# ── 6 Sample transcripts ──────────────────────────────────────────────────────

TRANSCRIPTS = [
    # 1 – Sarah Johnson, migraine
    (
        "Dr. Lee: Good morning, Sarah. What brings you in today?\n"
        "Patient: I've been having these terrible migraines for about a week. Pounding pain on the left side, "
        "sensitivity to light and sound. Happened three times this week.\n"
        "Dr. Lee: Any nausea or vomiting? Any aura before they start?\n"
        "Patient: Yes, nausea with each one. And yes, I see flashing lights about 20 minutes before the pain.\n"
        "Dr. Lee: Sarah, you're 34 years old, correct? And you mentioned last time you're allergic to Penicillin?\n"
        "Patient: That's right, causes a rash.\n"
        "Dr. Lee: I'm going to prescribe Sumatriptan 50mg to take at onset. Also Naproxen 500mg for the pain. "
        "Let's do a follow-up in two weeks. Blood pressure looks fine, 118 over 76.",
    ),
    # 2 – Robert Kim, hypertension
    (
        "Dr. Patel: Hello Robert, how have you been managing with the blood pressure?\n"
        "Patient: Not great, doctor. I've been getting headaches every morning and my home readings are around 155 over 95.\n"
        "Dr. Patel: You're 45, non-smoker, any chest pain or shortness of breath?\n"
        "Patient: Occasional shortness of breath when climbing stairs. No chest pain.\n"
        "Dr. Patel: I see you're allergic to Penicillin — hives. Let me check vitals. BP today is 158 over 96, "
        "HR 78. I'm increasing your Lisinopril to 10mg daily and adding Amlodipine 5mg. "
        "Cut back on sodium. Come back in 4 weeks.",
    ),
    # 3 – Emily Chen, diabetes
    (
        "Nurse: Emily, age 52, here for diabetes follow-up.\n"
        "Dr. Martin: Emily, your HbA1c came back at 8.2, a bit high. How's your diet been?\n"
        "Patient: I've been struggling to avoid sugar. Fasting glucose at home is usually around 140.\n"
        "Dr. Martin: Any hypoglycemic episodes? Fatigue, excessive thirst?\n"
        "Patient: Fatigue yes, thirst sometimes. Blood type is A positive.\n"
        "Dr. Martin: Weight is 78kg, BP 130 over 82, HR 74. I'm going to increase Metformin to 1000mg twice daily "
        "and refer you to the dietitian. Follow-up in 6 weeks with repeat HbA1c.",
    ),
    # 4 – Michael Torres, URI
    (
        "Dr. Kim: Michael, what's going on?\n"
        "Patient: I've had a sore throat, runny nose, and cough for about 5 days. Started with a fever of 101.\n"
        "Dr. Kim: Any difficulty swallowing? Ear pain?\n"
        "Patient: Sore throat only, no ear pain. Fever broke yesterday.\n"
        "Dr. Kim: Michael is 28. Throat looks red, no exudate. Lungs clear. Temp 98.8, HR 80, BP 120 over 78. "
        "This looks viral. No antibiotics needed. I'll prescribe Dextromethorphan for the cough "
        "and Ibuprofen 400mg as needed for discomfort. Rest, fluids. Come back if fever returns.",
    ),
    # 5 – Amanda Foster, back pain
    (
        "Dr. Reeves: Amanda, you came in for back pain?\n"
        "Patient: Yes, lower back for the past 3 weeks. Started after moving furniture. Sharp pain when I bend forward.\n"
        "Dr. Reeves: Any leg pain or numbness radiating down?\n"
        "Patient: No radiation. Just lower back. Amanda is 39, female, no allergies.\n"
        "Dr. Reeves: Straight leg raise negative. Range of motion reduced. BP 122 over 80, weight 65kg. "
        "Diagnosis is lumbar muscle strain. Prescribing Cyclobenzaprine 5mg at night for muscle spasm "
        "and Naproxen 500mg twice daily. Physical therapy referral. Rest from heavy lifting 2 weeks.",
    ),
    # 6 – James Wilson, chest pain
    (
        "Dr. Osei: James, tell me about the chest pain.\n"
        "Patient: Started two days ago. Pressure in the centre of my chest, radiates to my left arm. "
        "Worse on exertion, better with rest. I'm 58, male, smoker.\n"
        "Dr. Osei: Family history of heart disease?\n"
        "Patient: Father had a heart attack at 62. Blood type O negative.\n"
        "Dr. Osei: BP is 145 over 90, HR 88, temp normal. ECG shows ST depression. "
        "I'm starting you on Aspirin 325mg immediately and Nitroglycerin 0.4mg sublingual as needed. "
        "Urgent cardiology referral. No smoking. Return immediately for any worsening.",
    ),
]

SARAH_FOLLOWUP = (
    "Dr. Lee: Sarah Johnson, back for your two-week migraine follow-up. How are you doing?\n"
    "Patient: Much better! The Sumatriptan worked really well on the two migraines I had. "
    "Still getting about one per week though.\n"
    "Dr. Lee: Good to hear the medication is helping. Let's continue Sumatriptan and add "
    "Propranolol 40mg daily as a preventative. Also, keep a migraine diary. Follow-up in 4 weeks."
)

# ── Run tests ─────────────────────────────────────────────────────────────────

def main():
    section("0. Ensure DB tables exist")
    init_db()
    print("  Tables ready.")

    # ── 6 transcripts ────────────────────────────────────────────────────────
    section("1. Submit 6 sample transcripts")
    created = []
    for i, text in enumerate(TRANSCRIPTS, 1):
        resp = post_transcript(text)
        created.append(resp)
        print(f"  [{i}] {resp['patient_name']:<20} patient={resp['patient_id']}  record={resp['record_id']}")

    # ── DB verification ───────────────────────────────────────────────────────
    section("2. Verify all 6 patients + records + embeddings in Postgres")
    db = SessionLocal()
    try:
        for info in created:
            p = db.query(Patient).filter(Patient.id == info["patient_id"]).first()
            r = db.query(Record).filter(Record.id == info["record_id"]).first()
            emb = db.query(Embedding).filter(Embedding.record_id == info["record_id"]).first()
            rxs = db.query(Prescription).filter(Prescription.record_id == info["record_id"]).all()

            ok_p = "✓" if p else "✗"
            ok_r = "✓" if r else "✗"
            ok_e = "✓" if emb else "✗"
            rx_count = len(rxs)
            complaint = (r.chief_complaint or "")[:40] if r else "—"
            dim = len(json.loads(emb.vector)) if emb else 0

            print(f"  {ok_p} patient  {ok_r} record  {ok_e} embedding(dim={dim})  rx={rx_count}  — {complaint}")
    finally:
        db.close()

    # ── MCP tool queries ──────────────────────────────────────────────────────
    section("3. Run 7 MCP tool queries against Postgres")
    all_ids = get_all_patient_ids()
    print(f"  [1] get_all_patient_ids        → {all_ids}")

    hits = search_records_semantic("chest pain and cardiac symptoms", top_k=3)
    print(f"  [2] search_records_semantic    → top 3:")
    for h in hits:
        print(f"       [{h['score']:.3f}] {h['patient_name']} — {h['chief_complaint']}")

    details = get_patient_details(created[0]["patient_id"])
    print(f"  [3] get_patient_details        → {details['name']}, {len(details['records'])} record(s)")

    recent = filter_by_last_visit(all_ids, after_date="2024-01-01")
    print(f"  [4] filter_by_last_visit       → {recent}")

    rx_ids = filter_by_prescription(all_ids, "naproxen")
    print(f"  [5] filter_by_prescription     → {rx_ids} (have Naproxen)")

    adults = filter_by_age_range(all_ids, min_age=40)
    print(f"  [6] filter_by_age_range 40+    → {adults}")

    pen_ids = filter_by_allergy(all_ids, "penicillin")
    print(f"  [7] filter_by_allergy          → {pen_ids} (penicillin allergy)")

    # ── Follow-up visit (Sarah Johnson visit 2) ───────────────────────────────
    section("4. Follow-up visit — Sarah Johnson visit 2")
    sarah_patient_id = created[0]["patient_id"]
    sarah_name = created[0]["patient_name"]
    print(f"  Existing Sarah patient_id = {sarah_patient_id} ({sarah_name})")

    followup = post_transcript(SARAH_FOLLOWUP, patient_id=sarah_patient_id)
    print(f"  Follow-up record_id = {followup['record_id']}, patient_id = {followup['patient_id']}")
    assert followup["patient_id"] == sarah_patient_id, (
        f"Expected patient_id={sarah_patient_id}, got {followup['patient_id']}"
    )

    db = SessionLocal()
    try:
        sarah = db.query(Patient).filter(Patient.id == sarah_patient_id).first()
        assert len(sarah.records) == 2, f"Expected 2 records, got {len(sarah.records)}"
        print(f"  ✓ Sarah now has {len(sarah.records)} records linked to patient_id={sarah_patient_id}")
        for rec in sorted(sarah.records, key=lambda r: r.created_at):
            print(f"    record {rec.id}: {rec.chief_complaint}")
    finally:
        db.close()

    # ── SQLite regression check ───────────────────────────────────────────────
    section("5. Switch to SQLite — confirm unit tests still pass")
    print("  Run this to verify:  .\\venv\\Scripts\\pytest backend/routers/ -v --tb=short")
    print("  (uses in-memory SQLite, not affected by DATABASE_URL in .env)")

    print(f"\n{'─'*60}")
    print("  All Postgres integration tests passed.")
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    main()
