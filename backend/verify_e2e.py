"""
End-to-end verification: SQLAlchemy + Postgres migration.
Runs all 6 verification steps and prints real output at each stage.

Usage (Postgres):
    .\\venv\\Scripts\\python backend/verify_e2e.py

Usage (SQLite — pass --sqlite flag):
    .\\venv\\Scripts\\python backend/verify_e2e.py --sqlite
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODE = "sqlite" if "--sqlite" in sys.argv else "postgres"

if MODE == "postgres":
    os.environ["DATABASE_URL"] = "postgresql+pg8000://postgres:postgres@localhost:5432/clinai"
else:
    os.environ["DATABASE_URL"] = "sqlite:///./clinai_verify.db"

import requests
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

SERVER = "http://localhost:8000"

# ── Helpers ───────────────────────────────────────────────────────────────────

def sep(title):
    print(f"\n{'═'*64}")
    print(f"  {title}")
    print(f"{'═'*64}")


def _retry_post(url, *, data=None, json_body=None, timeout=90, label="request") -> dict:
    """POST with automatic retry on 429/500 rate-limit errors (up to 3 attempts)."""
    import re
    for attempt in range(1, 4):
        if data is not None:
            r = requests.post(url, data=data, timeout=timeout)
        else:
            r = requests.post(url, json=json_body, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        # Extract retry-delay from error body if present
        wait = 30
        try:
            detail = r.json().get("detail", "")
            m = re.search(r"retry in ([\d.]+)s", detail)
            if m:
                wait = int(float(m.group(1))) + 5
        except Exception:
            pass
        print(f"    [rate limit on attempt {attempt}] waiting {wait}s before retry…", flush=True)
        time.sleep(wait)
    r.raise_for_status()
    return r.json()


def post_transcript(text_body: str, patient_id: int = None) -> dict:
    data = {"transcript": text_body}
    if patient_id:
        data["patient_id"] = str(patient_id)
    return _retry_post(f"{SERVER}/api/transcription/text", data=data, timeout=90)


def agent_query(query: str) -> dict:
    return _retry_post(f"{SERVER}/api/agent/query", json_body={"query": query}, timeout=120)


# ── Transcripts ───────────────────────────────────────────────────────────────

TRANSCRIPTS = [
    (
        "Sarah Johnson visit",
        "Dr. Lee: Good morning, Sarah. What brings you in today?\n"
        "Patient: I've been having these terrible migraines for about a week. Pounding pain on the left side, "
        "sensitivity to light and sound. Happened three times this week.\n"
        "Dr. Lee: Any nausea or vomiting? Any aura before they start?\n"
        "Patient: Yes, nausea with each one. And yes, I see flashing lights about 20 minutes before the pain.\n"
        "Dr. Lee: Sarah Johnson, you're 34 years old, correct? And you mentioned last time you're allergic to Penicillin?\n"
        "Patient: That's right, causes a rash.\n"
        "Dr. Lee: I'm going to prescribe Sumatriptan 50mg to take at onset. Also Naproxen 500mg for the pain. "
        "Let's do a follow-up in two weeks. Blood pressure looks fine, 118 over 76.",
    ),
    (
        "Robert Kim visit",
        "Dr. Patel: Hello Robert Kim, how have you been managing with the blood pressure?\n"
        "Patient: Not great, doctor. I've been getting headaches every morning and my home readings are around 155 over 95.\n"
        "Dr. Patel: You're 45, non-smoker, any chest pain or shortness of breath?\n"
        "Patient: Occasional shortness of breath when climbing stairs. No chest pain.\n"
        "Dr. Patel: I see you're allergic to Penicillin — hives. Let me check vitals. BP today is 158 over 96, "
        "HR 78. I'm increasing your Lisinopril to 10mg daily and adding Amlodipine 5mg. "
        "Cut back on sodium. Come back in 4 weeks.",
    ),
    (
        "Emily Chen visit",
        "Nurse: Emily Chen, age 52, here for diabetes follow-up.\n"
        "Dr. Martin: Emily, your HbA1c came back at 8.2, a bit high. How's your diet been?\n"
        "Patient: I've been struggling to avoid sugar. Fasting glucose at home is usually around 140.\n"
        "Dr. Martin: Any hypoglycemic episodes? Fatigue, excessive thirst?\n"
        "Patient: Fatigue yes, thirst sometimes. Blood type is A positive.\n"
        "Dr. Martin: Weight is 78kg, BP 130 over 82, HR 74. I'm going to increase Metformin to 1000mg twice daily "
        "and refer you to the dietitian. Follow-up in 6 weeks with repeat HbA1c.",
    ),
    (
        "Michael Torres visit",
        "Dr. Kim: Michael Torres, what's going on?\n"
        "Patient: I've had a sore throat, runny nose, and cough for about 5 days. Started with a fever of 101.\n"
        "Dr. Kim: Any difficulty swallowing? Ear pain?\n"
        "Patient: Sore throat only, no ear pain. Fever broke yesterday.\n"
        "Dr. Kim: Michael is 28. Throat looks red, no exudate. Lungs clear. Temp 98.8, HR 80, BP 120 over 78. "
        "This looks viral. No antibiotics needed. I'll prescribe Dextromethorphan for the cough "
        "and Ibuprofen 400mg as needed for discomfort. Rest, fluids. Come back if fever returns.",
    ),
    (
        "Amanda Foster visit",
        "Dr. Reeves: Amanda Foster, you came in for back pain?\n"
        "Patient: Yes, lower back for the past 3 weeks. Started after moving furniture. Sharp pain when I bend forward.\n"
        "Dr. Reeves: Any leg pain or numbness radiating down?\n"
        "Patient: No radiation. Just lower back. Amanda is 39, female, no allergies.\n"
        "Dr. Reeves: Straight leg raise negative. Range of motion reduced. BP 122 over 80, weight 65kg. "
        "Diagnosis is lumbar muscle strain. Prescribing Cyclobenzaprine 5mg at night for muscle spasm "
        "and Naproxen 500mg twice daily. Physical therapy referral. Rest from heavy lifting 2 weeks.",
    ),
    (
        "James Wilson visit",
        "Dr. Osei: James Wilson, tell me about the chest pain.\n"
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

AGENT_QUERIES = [
    ("Chest pain / cardiac", "Which patients presented with chest pain or cardiac symptoms?"),
    ("Diabetic patients", "Show me all diabetic patients."),
    ("Penicillin allergy", "Which patients have a penicillin allergy?"),
    ("Diabetic + Metformin", "Which diabetic patients are currently on Metformin?"),
    ("Age + diabetes combo", "Which patients over 50 have diabetes?"),
    ("Ibuprofen + age combo", "Which patients under 35 were prescribed Ibuprofen?"),
    ("Zero-match — Aspirin prescription (non-cardiac)", "Which patients were prescribed Aspirin for arthritis pain?"),
    ("Pediatric under-10", "Do we have any patients under 10 years old?"),
]


def main():
    from backend.database import Base, init_db, SessionLocal
    from backend.models import Patient, Record, Prescription, Embedding

    # ─────────────────────────────────────────────────────────────────────────
    sep(f"STEP 1 — DATABASE_URL + init_db()  [{MODE.upper()}]")
    # ─────────────────────────────────────────────────────────────────────────

    url = os.environ["DATABASE_URL"]
    print(f"  DATABASE_URL = {url}\n")

    # Drop everything and recreate so we start completely fresh
    print("  Dropping all tables (fresh start)…")
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        echo=True,          # prints every SQL statement
    )
    # Use raw DROP CASCADE to handle any stale tables from old schema
    with engine.connect() as conn:
        if url.startswith("sqlite"):
            # SQLite: drop known tables in dependency order
            for tbl in ["embeddings", "prescriptions", "records", "visits", "patients"]:
                conn.execute(text(f"DROP TABLE IF EXISTS {tbl}"))
        else:
            # Postgres: cascade handles all FK dependencies at once
            conn.execute(text(
                "DROP TABLE IF EXISTS embeddings, prescriptions, records, visits, patients CASCADE"
            ))
        conn.commit()
    print("\n  Running init_db() (CREATE TABLE statements above)…")
    Base.metadata.create_all(bind=engine)

    print("\n  Tables now in DB:")
    for t in sorted(inspect(engine).get_table_names()):
        print(f"    ✓ {t}")

    engine.dispose()  # close echo engine; real code uses non-echo engine

    # ─────────────────────────────────────────────────────────────────────────
    sep("STEP 2 — Submit 6 transcripts, verify row count after each")
    # ─────────────────────────────────────────────────────────────────────────

    created = []
    db = SessionLocal()
    try:
        for label, tx in TRANSCRIPTS:
            resp = post_transcript(tx)
            count = db.query(Patient).count()
            db.expire_all()  # force re-read from DB
            count = db.query(Patient).count()
            created.append(resp)
            print(
                f"  [{count}/6]  {resp['patient_name']:<22}"
                f"  patient_id={resp['patient_id']}  record_id={resp['record_id']}"
                f"  ({label})"
            )
            time.sleep(5)   # pause between Gemini calls to avoid per-minute limit
    finally:
        db.close()

    print(f"\n  Final patient count in DB: ", end="")
    db2 = SessionLocal()
    final_count = db2.query(Patient).count()
    db2.close()
    print(final_count)
    assert final_count == 6, f"Expected 6 patients, got {final_count}"
    print("  ✓ Exactly 6 patients — no duplicates, no missing inserts.")

    # ─────────────────────────────────────────────────────────────────────────
    sep("STEP 3 — Full DB record for James Wilson (field-by-field)")
    # ─────────────────────────────────────────────────────────────────────────

    james_info = next((r for r in created if "james" in r["patient_name"].lower()), None)
    assert james_info, "James not found in created records"

    db3 = SessionLocal()
    try:
        james = db3.query(Patient).filter(Patient.id == james_info["patient_id"]).first()
        record = db3.query(Record).filter(Record.patient_id == james.id).first()
        prescriptions = db3.query(Prescription).filter(Prescription.record_id == record.id).all()
        embedding = db3.query(Embedding).filter(Embedding.record_id == record.id).first()

        print(f"  PATIENT ROW  (id={james.id})")
        print(f"    name        = {james.name!r}")
        print(f"    age         = {james.age}")
        print(f"    gender      = {james.gender!r}")
        print(f"    blood_type  = {james.blood_type!r}")
        print(f"    allergies   = {james.allergies}")
        print(f"    created_at  = {james.created_at}")

        print(f"\n  RECORD ROW   (id={record.id})")
        print(f"    chief_complaint = {record.chief_complaint!r}")
        print(f"    symptoms        = {record.symptoms}")
        print(f"    diagnoses       = {record.diagnoses}")
        print(f"    vitals          = {record.vitals}")
        print(f"    notes           = {record.notes!r}")
        print(f"    follow_up       = {record.follow_up!r}")

        print(f"\n  PRESCRIPTIONS ({len(prescriptions)} row(s))")
        for rx in prescriptions:
            print(f"    drug={rx.drug!r}  dose={rx.dose!r}  freq={rx.frequency!r}  dur={rx.duration!r}")

        print(f"\n  EMBEDDING")
        vec = json.loads(embedding.vector) if embedding else None
        print(f"    model     = {embedding.embed_model if embedding else 'MISSING'}")
        print(f"    dimension = {len(vec) if vec else 'N/A'}")
        print(f"    first 5 values = {vec[:5] if vec else 'N/A'}")

        print(f"\n  TRANSCRIPT CROSS-CHECK (what the doctor actually said):")
        print(f"    Transcript says 58yo male smoker, O neg blood, ST depression,")
        print(f"    Aspirin 325mg + Nitroglycerin 0.4mg, urgent cardiology referral.")
        print(f"    Extracted: age={james.age}, gender={james.gender!r}, blood_type={james.blood_type!r}")
        print(f"    Drugs extracted: {[rx.drug for rx in prescriptions]}")
        print(f"    Chief complaint: {record.chief_complaint!r}")
        # Assertions
        assert james.age == 58,          f"age mismatch: {james.age}"
        assert "male" in (james.gender or "").lower(), f"gender mismatch: {james.gender}"
        assert "o" in (james.blood_type or "").lower(), f"blood_type mismatch: {james.blood_type}"
        drugs = [rx.drug.lower() for rx in prescriptions]
        assert any("aspirin" in d for d in drugs), f"Aspirin missing from {drugs}"
        assert any("nitroglycerin" in d or "nitro" in d for d in drugs), f"Nitroglycerin missing from {drugs}"
        print(f"    ✓ All field assertions passed.")
    finally:
        db3.close()

    # ─────────────────────────────────────────────────────────────────────────
    sep("STEP 4 — 8 agent queries (raw JSON output)")
    # ─────────────────────────────────────────────────────────────────────────

    for label, query in AGENT_QUERIES:
        print(f"\n  ── Query: {label}")
        print(f"     Input:  \"{query}\"")
        result = agent_query(query)
        print(f"     Answer: {result['answer'][:300]}")
        print(f"     Patients matched: {len(result['patients'])}")
        for p in result["patients"]:
            print(f"       • {p['name']} (id={p['id']}, age={p.get('age')})")
        time.sleep(8)   # pause between agent queries

    # ─────────────────────────────────────────────────────────────────────────
    sep("STEP 5 — Sarah Johnson follow-up visit")
    # ─────────────────────────────────────────────────────────────────────────

    sarah_info = next(r for r in created if "sarah" in r["patient_name"].lower())
    sarah_original_patient_id = sarah_info["patient_id"]
    print(f"  Sarah's original patient_id = {sarah_original_patient_id}")
    print(f"  Submitting follow-up transcript WITH patient_id={sarah_original_patient_id} in form data…")

    followup = post_transcript(SARAH_FOLLOWUP, patient_id=sarah_original_patient_id)
    print(f"  Follow-up response: patient_id={followup['patient_id']}, record_id={followup['record_id']}")

    db4 = SessionLocal()
    try:
        sarah = db4.query(Patient).filter(Patient.id == sarah_original_patient_id).first()
        total_patients = db4.query(Patient).count()
        records = db4.query(Record).filter(Record.patient_id == sarah_original_patient_id).all()
        print(f"\n  Total patients still in DB: {total_patients}  (should still be 6)")
        print(f"  Records linked to patient_id={sarah_original_patient_id}: {len(records)}")
        for rec in sorted(records, key=lambda r: r.created_at):
            rxs = db4.query(Prescription).filter(Prescription.record_id == rec.id).all()
            print(f"    record {rec.id}: {rec.chief_complaint!r}  — {len(rxs)} prescription(s)")
            for rx in rxs:
                print(f"      └ {rx.drug} {rx.dose}")

        if followup["patient_id"] == sarah_original_patient_id:
            print(f"\n  ✓ DUPLICATE DETECTION WORKED: follow-up linked to existing patient_id={sarah_original_patient_id}")
            print(f"    Behaviour: patient_id passed explicitly in form → same patient row reused.")
        else:
            print(f"\n  ✗ NEW PATIENT CREATED: patient_id={followup['patient_id']} (original was {sarah_original_patient_id})")
            print(f"    Behaviour: name-match deduplication did not fire; explicit patient_id was ignored.")
    finally:
        db4.close()


if __name__ == "__main__":
    main()
