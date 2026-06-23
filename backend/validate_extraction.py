"""
Validates extraction quality for POST /api/transcription/text.
Sends 10 clinical transcripts and checks whether 6 fields were
successfully populated: demographics, chief_complaint, symptoms,
diagnoses, prescriptions, vitals.

Usage:
    .\\venv\\Scripts\\python backend/validate_extraction.py

Against a deployed instance:
    .\\venv\\Scripts\\python backend/validate_extraction.py --server=https://your-app.onrender.com
"""

import sys
import requests

SERVER = next(
    (a.split("=", 1)[1] for a in sys.argv if a.startswith("--server=")),
    "http://localhost:8000",
)
URL = f"{SERVER}/api/transcription/text"

TRANSCRIPTS = [
    (
        "Prescription renewal — minimal info",
        "Dr. Adams: Quick renewal today. BP is 128 over 80. Renewing Amlodipine 5mg for "
        "three months. Patient is Sarah Nguyen, 54 years old. No side effects reported.",
    ),
    (
        "Strep throat — paediatric",
        "Patient is Jake Mercer, 19 years old. Sore throat for three days, mild fever 100.4, "
        "right tonsil exudate. Rapid strep test positive. Prescribed Amoxicillin 500mg three "
        "times daily for ten days. Paracetamol for fever. HR 82, weight 71kg.",
    ),
    (
        "UTI — adult female",
        "Mrs. Carter, 42 years old, presents with dysuria and urinary frequency for two days. "
        "No fever, no back pain. Urine dipstick positive for nitrites and leucocytes. "
        "No allergies. Prescribed Trimethoprim 200mg twice daily for seven days. "
        "BP 118 over 76, HR 74.",
    ),
    (
        "Hypertension review — medication switch",
        "Mr. Brennan, 61 years old. Annual hypertension review. Home BP 148 over 90. "
        "Dry cough on Lisinopril 10mg — switching to Losartan 50mg. LDL 3.9, starting "
        "Atorvastatin 20mg at night. HbA1c 5.8, pre-diabetic. Weight 94kg, BMI 30. "
        "BP today 146 over 92, HR 78.",
    ),
    (
        "Paediatric asthma — step up",
        "Sophie Williams, 8 years old. Nocturnal cough three times per week, using Salbutamol "
        "before PE daily. Chest tightness in mornings. Poorly controlled asthma. Starting "
        "Beclomethasone 50mcg two puffs twice daily via spacer. Continue Salbutamol as needed. "
        "No known allergies. RR 18, O2 sats 99%.",
    ),
    (
        "Hypothyroidism — new diagnosis",
        "Mrs. Lawson, 55 years old. Fatigue, 7kg weight gain, hair loss, dry skin, constipation. "
        "TSH 12.4, free T4 9.2 — hypothyroidism confirmed. Starting Levothyroxine 50mcg once "
        "daily on empty stomach. Penicillin allergy — rash. BP 118 over 74, HR 58, weight 78kg. "
        "Blood type O positive.",
    ),
    (
        "Type 2 diabetes — new diagnosis",
        "Mr. Nkomo, 49 years old. Polydipsia, polyuria, 5kg weight loss, blurred vision. "
        "Fasting glucose 14.2, HbA1c 10.1. New diagnosis Type 2 Diabetes Mellitus. "
        "Starting Metformin 500mg twice daily with meals, increasing to 1000mg after one month. "
        "No drug allergies. Blood type B negative. Weight 102kg, BMI 33, BP 142 over 88.",
    ),
    (
        "NSTEMI — emergency presentation",
        "Mr. Flynn, 63 years old. Crushing central chest pain radiating to left arm and jaw on "
        "exertion, 10 minutes duration, with diaphoresis and nausea. Ex-smoker 30 years. "
        "Atorvastatin 40mg. Codeine allergy — confusion and drowsiness. Blood type A positive. "
        "ECG ST depression V4-V6. Troponin I 0.08. BP 158 over 96, HR 92, O2 sats 97%. "
        "NSTEMI. Aspirin 300mg, Ticagrelor 180mg, Fondaparinux, Metoprolol 25mg.",
    ),
    (
        "Complex multimorbidity — annual review",
        "Mr. Petrov, 72 years old. Heart failure on Bisoprolol 5mg, Ramipril 10mg, "
        "Spironolactone 25mg, Furosemide 80mg. BNP 280, stable. Left knee osteoarthritis — "
        "NSAIDs contraindicated. Referring to orthopaedics. Bereavement low mood after wife's "
        "death — referring to grief counselling. Type 2 Diabetes HbA1c 7.2 on Metformin 1000mg. "
        "AF rate-controlled on Bisoprolol, anticoagulated with Apixaban 5mg twice daily. "
        "No drug allergies. Blood type A negative. BP 126 over 74, weight 78kg, HR 74.",
    ),
    (
        "New patient intake — headache and anxiety",
        "Fatima Al-Rashid, 38 years old. Tension-type headaches daily for six months, "
        "pressure quality, worse end of day, Paracetamol 4-5 days per week. "
        "Insomnia, occupational anxiety, previous Sertraline 50mg. "
        "Appendectomy age 22, Caesarean section age 35. Mother has T2DM and hypertension. "
        "Amoxicillin allergy — rash. Blood type AB positive. "
        "BP 122 over 78, HR 76, weight 64kg, BMI 24.1. "
        "Plan: headache diary, limit analgesia, refer to IAPT for CBT, "
        "repeat FBC and ferritin for iron deficiency anaemia.",
    ),
]

FIELDS = ["demographics", "chief_complaint", "symptoms", "diagnoses", "prescriptions", "vitals"]


def _check_demographics(extracted: dict) -> bool:
    p = extracted.get("patient", {})
    return bool(p.get("name") or p.get("age") or p.get("gender"))


def _check_field(field: str, extracted: dict) -> bool:
    visit = extracted.get("visit", {})
    if field == "demographics":
        return _check_demographics(extracted)
    if field == "chief_complaint":
        return bool(visit.get("chief_complaint", "").strip())
    if field == "symptoms":
        val = visit.get("symptoms", [])
        return isinstance(val, list) and len(val) > 0
    if field == "diagnoses":
        val = visit.get("diagnoses", [])
        return isinstance(val, list) and len(val) > 0
    if field == "prescriptions":
        val = visit.get("prescriptions", [])
        return isinstance(val, list) and len(val) > 0
    if field == "vitals":
        v = visit.get("vitals", {})
        return isinstance(v, dict) and any(v.get(k) for k in ("bp", "hr", "temp", "weight", "height"))
    return False


def run():
    print(f"\nTarget : {URL}")
    print(f"Samples: {len(TRANSCRIPTS)}\n")

    col_w = 36
    header = f"{'Transcript':<{col_w}}" + "".join(f"{f:>15}" for f in FIELDS)
    print(header)
    print("─" * len(header))

    # field_hits[field] = number of transcripts where field was present
    field_hits = {f: 0 for f in FIELDS}
    successful = 0
    errors = []

    for i, (label, transcript) in enumerate(TRANSCRIPTS, 1):
        short_label = f"{i}. {label}"[:col_w - 1]
        try:
            r = requests.post(URL, data={"transcript": transcript}, timeout=120)
            if r.status_code != 200:
                errors.append(f"  [{i}] HTTP {r.status_code}: {label}")
                print(f"{short_label:<{col_w}}" + "".join(f"{'ERR':>15}" for _ in FIELDS))
                continue

            extracted = r.json().get("extracted", {})
            successful += 1
            row = f"{short_label:<{col_w}}"
            for field in FIELDS:
                ok = _check_field(field, extracted)
                if ok:
                    field_hits[field] += 1
                row += f"{'✓':>15}" if ok else f"{'✗':>15}"
            print(row)

        except requests.exceptions.Timeout:
            errors.append(f"  [{i}] TIMEOUT: {label}")
            print(f"{short_label:<{col_w}}" + "".join(f"{'TIMEOUT':>15}" for _ in FIELDS))
        except requests.exceptions.ConnectionError:
            errors.append(f"  [{i}] NO SERVER: {label}")
            print(f"{short_label:<{col_w}}" + "".join(f"{'NO CONN':>15}" for _ in FIELDS))

    if successful == 0:
        print("\nNo successful requests — is the server running?")
        return

    # ── Field-level report ────────────────────────────────────────────────────
    print("\n" + "─" * len(header))
    print(f"\nField-level accuracy  ({successful} successful requests)\n")
    all_rates = []
    for field in FIELDS:
        rate = field_hits[field] / successful
        all_rates.append(rate)
        bar = "█" * round(rate * 20)
        print(f"  {field:<16} {field_hits[field]:>2}/{successful}  {rate:>6.1%}  {bar}")

    overall = sum(all_rates) / len(all_rates)
    total_checks = successful * len(FIELDS)
    total_hits = sum(field_hits.values())
    print(f"\n  Overall extraction rate: {total_hits}/{total_checks} checks passed  ({overall:.1%})")

    if errors:
        print("\nErrors:")
        for e in errors:
            print(e)
    print()


if __name__ == "__main__":
    run()
