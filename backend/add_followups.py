"""
Add follow-up visits to existing patients.
Links each transcript to the correct patient_id so records accumulate
under the same patient rather than creating duplicates.

Usage:
    .\\venv\\Scripts\\python backend/add_followups.py
"""

import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+pg8000://postgres:postgres@localhost:5432/clinai",
)

import requests

SERVER = "http://localhost:8000"


def sep(title):
    print(f"\n{'═'*64}\n  {title}\n{'═'*64}")


def _retry_post(url, data, timeout=90):
    for attempt in range(1, 4):
        r = requests.post(url, data=data, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        wait = 30
        try:
            m = re.search(r"retry in ([\d.]+)s", r.json().get("detail", ""))
            if m:
                wait = int(float(m.group(1))) + 5
        except Exception:
            pass
        print(f"  [rate limit attempt {attempt}] waiting {wait}s…", flush=True)
        time.sleep(wait)
    r.raise_for_status()


def submit(label, patient_id, transcript):
    print(f"\n  {label} (patient_id={patient_id}) …", flush=True)
    resp = _retry_post(
        f"{SERVER}/api/transcription/text",
        data={"transcript": transcript, "patient_id": str(patient_id)},
    )
    print(f"  → record_id={resp['record_id']}  patient={resp['patient_name']!r}")
    time.sleep(6)
    return resp


# ── Follow-up transcripts ─────────────────────────────────────────────────────

FOLLOWUPS = [
    (
        "Robert Kim — 4-week BP follow-up",
        2,  # Robert Kim
        """
Dr. Patel: Robert Kim, good to see you. Four weeks since we increased your Lisinopril and
added Amlodipine. How have you been feeling?

Patient: Much better actually. The morning headaches have almost completely gone. I've been
checking my blood pressure twice a day and it's been mostly between 132 and 140 over 85.
That's a big improvement from 158 over 96.

Dr. Patel: That is a significant improvement. Any side effects from the new medications?
Ankle swelling from the Amlodipine? Dry cough from the Lisinopril?

Patient: A tiny bit of ankle puffiness in the evenings, but nothing that bothers me. No cough.
I've also cut back on salt quite a lot — my wife has been very supportive, cooking differently.

Dr. Patel: Excellent. Your blood results came back — sodium is normal, potassium is 4.1 which
is fine, creatinine is 1.0 — kidneys happy with the ACE inhibitor. BP today is 136 over 84.
Heart rate 72. That's a great response. I want to keep you on the same medications — Lisinopril
10mg and Amlodipine 5mg — and review again in three months. Keep up the dietary changes. If
you get any ankle swelling that's uncomfortable, call us.

Patient: Will do. Thank you, doctor.
""",
    ),
    (
        "Emily Chen — 6-week diabetes follow-up with HbA1c",
        3,  # Emily Chen
        """
Nurse: Emily Chen, age 52, follow-up for diabetes management.

Dr. Martin: Emily, your six-week repeat HbA1c results are back. It's come down to 7.6 from
8.2 — that's real progress. How have you been getting on with the increased Metformin dose?

Patient: I did have some stomach upset in the first two weeks. Nausea mainly, especially in
the mornings. But that's settled now. I've been seeing the dietitian as well — she's been
very helpful with meal planning.

Dr. Martin: The GI side effects usually settle after two to three weeks, which is exactly what
you experienced. The dietitian referral was clearly worthwhile. How are your home glucose
readings?

Patient: Fasting readings are between 115 and 130 now. After meals around 160 to 180. Still
a bit high but much better than 210.

Dr. Martin: Definitely moving in the right direction. Weight today is 76.5kg — you've lost
1.5kg. BP 126 over 80. HbA1c at 7.6 — our target is below 7, so we're getting closer.
Let's keep you on Metformin 1000mg twice daily. I'm not changing anything else today —
the trajectory is good. Another HbA1c in eight weeks. Keep working with the dietitian.
Any hypoglycaemic episodes?

Patient: No, nothing like that. I feel much more energetic actually.

Dr. Martin: That's the improved glucose control making a difference. Great work, Emily.
""",
    ),
    (
        "James Wilson — cardiology post-referral follow-up",
        6,  # James Wilson
        """
Dr. Osei: James Wilson, good to see you back. I have the cardiology report here from
St. Thomas' Hospital. Tell me how you've been since the referral.

Patient: It's been quite a journey. The cardiologist did an angiogram — they found one
blockage in the left anterior descending artery, about 70 percent. They put a stent in
three weeks ago. I was in hospital for two nights. Since then, the chest pain has
completely gone. It's remarkable, honestly.

Dr. Osei: That's excellent news. The LAD stent should give you good long-term relief.
You're on dual antiplatelet therapy now — Aspirin and Clopidogrel — don't stop either
of those without speaking to us or the cardiologist, even if you have a procedure coming
up. Have you managed to stop smoking?

Patient: I haven't had a cigarette since the day before the angiogram. Three weeks smoke-free.
The heart attack scare — well, the near miss — that was enough for me.

Dr. Osei: Three weeks is brilliant. Well done. That's the single most impactful thing you
can do for your heart. BP today is 130 over 82 — much better than 145 over 90 last visit.
HR 68. I'm adding Atorvastatin 40mg at night for cholesterol protection, and Ramipril 5mg
for heart muscle protection post-stent. Continue Aspirin 75mg daily — we'll keep the
Nitroglycerin as needed but hopefully you won't need it. Cardiology want to see you in
six months. Come back to me in four weeks for blood results.

Patient: Thank you, doctor. I feel like I've been given a second chance.

Dr. Osei: Use it well. No smoking, low sodium diet, gentle exercise as the cardiologist
advised. Any chest pain at all — call 999 immediately.
""",
    ),
    (
        "Amanda Foster — 2-week back pain follow-up",
        5,  # Amanda Foster
        """
Dr. Reeves: Amanda Foster, back for your two-week review. How's the lower back been?

Patient: Honestly much better. The Cyclobenzaprine knocks me out at night which I wasn't
expecting, but it does help the muscle spasm. The Naproxen helps during the day. I've
been to physio twice and they've given me a set of exercises.

Dr. Reeves: Good. The drowsiness from Cyclobenzaprine is expected — that's why we give it
only at night. Are you doing the physio exercises consistently?

Patient: Every morning, yes. The physio said my core is quite weak which is probably why
my back went when moving furniture. She's got me doing dead bugs and bird dogs — it feels
strange but I can feel it working.

Dr. Reeves: Those are exactly the right exercises for lumbar stability. Range of motion
today — you can touch your knees on forward flexion, which is better than last time when
you could barely bend at all. Straight leg raise still negative — no nerve involvement.
Tenderness on palpation has reduced.

I'm happy to stop the Cyclobenzaprine now — two weeks is usually sufficient for acute
muscle spasm, and we don't want to use it long term. Continue Naproxen 500mg as needed
for pain, not routinely. Carry on with physio — I'd suggest four more sessions at least.
No heavy lifting for another two weeks, then you can start building back gradually.

Patient: Can I start running again? I used to run three times a week.

Dr. Reeves: Give it another three weeks then start with walking briskly for ten minutes
and build from there. If you get any shooting pain down the leg, come back immediately.
Otherwise, I don't need to see you again unless things worsen.
""",
    ),
    (
        "David Okonkwo — 4-week renal and metabolic review",
        10,  # David Okonkwo
        """
Dr. Reyes: David Okonkwo, good morning. Four weeks since your last visit when we made
several medication changes. Blood results are back — let's go through them together.

Patient: Morning, doctor. The ankle swelling is much better since the Furosemide. I'm
going to the bathroom more but I take it at 7am so it's all done by afternoon.

Dr. Reyes: That's exactly right, good. Now the results — HbA1c has come down slightly
to 8.4 from 8.7. Early days with the Empagliflozin, it usually takes three to six months
for full effect. Kidney function — eGFR is 50, up from 48, which is mildly reassuring.
Creatinine 1.54. BP today is 142 over 88, down from 158 over 94. The Losartan increase
to 100mg is working. Potassium is 4.8 — slightly high but still within normal range —
we'll watch that with the Losartan.

Patient: The ankle swelling is completely gone now, by the way. And the shortness of
breath on exertion is better — I walked to the post office yesterday which I couldn't
have done a month ago.

Dr. Reyes: That's very encouraging — the Furosemide has cleared the fluid load and your
heart is working more efficiently. CK level was normal — no muscle damage from the
Atorvastatin, so we can continue that. Weight is 86.5kg, down 2.5kg — some of that is
fluid. Let's keep everything the same for now. Repeat bloods in six weeks. Have you
seen the renal dietitian?

Patient: Yes, I had my appointment. She's given me a low-sodium meal plan and I've
cut out processed foods almost entirely. My wife is very pleased with the new cooking.

Dr. Reyes: Excellent. Keep up that momentum. See you in six weeks.
""",
    ),
    (
        "Marcus Thompson — 6-week COPD and mental health review",
        12,  # Marcus Thompson
        """
Dr. Osei: Marcus Thompson, come in. Six weeks since we last met and made quite a few
changes. How are you doing?

Patient: A lot better on multiple fronts, honestly. The new combination inhaler has made
a real difference — I'm using the blue rescue inhaler maybe once a day now, sometimes not
at all. Before, it was six to eight times. That's a huge change.

Dr. Osei: That's an excellent response to the Salmeterol/Fluticasone combination. Once
a day is within the acceptable range. Are you rinsing your mouth after each use?

Patient: Yes, religiously. You scared me about the oral thrush.

Dr. Osei: Good. How about the Sertraline increase and the Buspirone? The mental health side?

Patient: The anxiety has been more manageable. I've had maybe two bad episodes in six
weeks, compared to almost daily before. The Lorazepam — I've been using it only once in
the past three weeks. Down from twice a week.

Dr. Osei: That's a really meaningful reduction. The Buspirone is working as we hoped.
I want to taper the Lorazepam completely over the next four weeks — I'll give you a
specific schedule. Spirometry today: FEV1 is 62 percent of predicted, up from 58 percent
six weeks ago. Oxygen saturation 96 percent — also improved from 94. BP 126 over 80,
HR 74. Weight stable at 82kg.

Now — smoking. You were on five cigarettes a day last visit.

Patient: Three now. I've downloaded a quit app. My daughter is tracking me.

Dr. Osei: Three is progress. I want to prescribe Varenicline — Champix — today. Start
with 0.5mg once daily for three days, then 0.5mg twice daily for four days, then 1mg
twice daily. Pick a quit date in the next two weeks. It's the most effective cessation
medication we have. Any mood changes while on it, contact us immediately.

Patient: I'll try it. I really will.

Dr. Osei: I believe you. See you in six weeks. And don't hesitate to call if the
anxiety spikes — that's what we're here for.
""",
    ),
]


def main():
    sep(f"ADDING {len(FOLLOWUPS)} FOLLOW-UP VISITS")
    for label, patient_id, transcript in FOLLOWUPS:
        submit(label, patient_id, transcript)

    sep("DONE")
    print(f"\n  {len(FOLLOWUPS)} follow-up records added successfully.")


if __name__ == "__main__":
    main()
