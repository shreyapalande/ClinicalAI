"""
Extended patient load + complex MCP agent query test.

Adds 3 new patients with detailed 10-minute transcripts, then runs
cross-patient agentic queries that require chaining multiple MCP tools.

Usage (patients already in DB from verify_e2e.py):
    .\\venv\\Scripts\\python backend/test_complex.py

Usage (skip transcript submission, only run queries):
    .\\venv\\Scripts\\python backend/test_complex.py --queries-only
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
QUERIES_ONLY = "--queries-only" in sys.argv


# ── Helpers ───────────────────────────────────────────────────────────────────

def sep(title):
    print(f"\n{'═'*64}")
    print(f"  {title}")
    print(f"{'═'*64}")


def _retry_post(url, *, data=None, json_body=None, timeout=120) -> dict:
    for attempt in range(1, 4):
        r = (
            requests.post(url, data=data, timeout=timeout)
            if data is not None
            else requests.post(url, json=json_body, timeout=timeout)
        )
        if r.status_code == 200:
            return r.json()
        wait = 30
        try:
            m = re.search(r"retry in ([\d.]+)s", r.json().get("detail", ""))
            if m:
                wait = int(float(m.group(1))) + 5
        except Exception:
            pass
        print(f"    [rate limit attempt {attempt}] waiting {wait}s…", flush=True)
        time.sleep(wait)
    r.raise_for_status()
    return r.json()


def post_transcript(text_body: str) -> dict:
    return _retry_post(f"{SERVER}/api/transcription/text", data={"transcript": text_body})


def agent_query(query: str) -> dict:
    return _retry_post(f"{SERVER}/api/agent/query", json_body={"query": query})


# ── New patient transcripts ────────────────────────────────────────────────────

NEW_PATIENTS = [
    (
        "David Okonkwo — diabetes + hypertension + CKD",
        """
Dr. Reyes: Good morning, Mr. David Okonkwo. I'm Dr. Reyes. Please, have a seat. So today we're
here for your quarterly review — you're 67 years old, correct? How have you been feeling overall
since your last visit?

Patient: Morning, doctor. That's right, 67. Honestly, some days are better than others. The
fatigue has been quite bad lately. I've been getting tired just walking from the car park to my
office. I know things slow down, but this feels like more than just age.

Dr. Reyes: I understand. You mentioned fatigue — are you having any shortness of breath with
that exertion, or is it purely tiredness in your legs and body?

Patient: Both, actually. Some shortness of breath. Not at rest, just when I'm moving. My ankles
have also been swollen by the evening, which my wife pointed out. She's been keeping a close eye
on me since my diabetes diagnosis last year.

Dr. Reyes: Okay, that's important. Any chest pain, palpitations, or dizziness?

Patient: No chest pain. I get a little lightheaded sometimes when I stand up quickly, but that
passes in a few seconds. No palpitations that I notice.

Dr. Reyes: Right, that postural dizziness is worth watching. Let's talk about your blood sugars.
You're on Metformin 1000mg twice daily. Are you checking at home?

Patient: Yes, I have the glucometer. Fasting readings have been between 145 and 170 most mornings.
After meals it goes up to around 210 sometimes. I know those aren't great numbers. I've been
trying with the diet, but my wife cooks Nigerian food and it's hard to avoid the rice and yam.

Dr. Reyes: I appreciate that context — food is cultural, not just nutritional. We'll factor that
in. Your last HbA1c came back at 8.7, which is higher than we'd like. We had it at 8.1 three
months ago, so it has crept up. Now, alongside the diabetes, you've had high blood pressure for
about six years now. You're on Losartan 50mg and Amlodipine 5mg. How are the blood pressure
readings at home?

Patient: Mostly around 148 to 155 over 92. I take it every morning. Sometimes 160 in the evenings
if I've had a stressful day at work. I'm a retired accountant but I still do some consultancy, so
it's not always relaxed.

Dr. Reyes: I see. And the kidney function — you know we've been monitoring that closely because
Metformin needs to be used carefully when kidneys aren't working at full capacity. Your last
creatinine was 1.6 and eGFR was 48, which puts you at CKD stage 3a. We need to keep a close
eye on that. Have you been keeping well hydrated?

Patient: I try to drink water. Probably not as much as I should. Maybe four or five glasses a day.

Dr. Reyes: We'd want closer to eight. The kidneys need that. Also, I want to ask about your
cholesterol — you're on Atorvastatin 40mg. Any muscle aches or cramps since starting that?

Patient: My calves ache sometimes at night. I wasn't sure if that was the tablets or just old age.

Dr. Reyes: It's worth investigating. Statins can cause myalgia. Let me check your CK levels today.
Now, do you have any known drug allergies?

Patient: No known allergies to any medicines. I've taken various things over the years without
any reactions.

Dr. Reyes: And blood type — do you know it?

Patient: B positive, yes. They told me when I donated blood years ago.

Dr. Reyes: Great. Let me do a quick examination. BP today is 158 over 94 — higher than we want.
Heart sounds normal, no murmurs. Slight pitting oedema in both ankles, grade 1. Lungs are clear.
Abdomen soft. Weight is 89 kilograms, height 175cm, so BMI is about 29 — overweight but not
obese. Peripheral pulses present and equal.

I'm going to make several changes today. First, I want to increase your Losartan to 100mg daily
to get better blood pressure control — that will also give more kidney protection. Second, because
your HbA1c has risen, I'm adding Empagliflozin 10mg once daily to your diabetes regimen. It has
good evidence for heart and kidney protection in people with diabetes and CKD, which is exactly
your profile. I'm keeping the Metformin for now but if your eGFR drops below 45 we'll need to
stop it. Third, I want to add Furosemide 20mg in the morning for those ankle swellings — that
could also be contributing to the shortness of breath on exertion.

We'll repeat bloods in four weeks including kidney function, HbA1c, lipid panel, and CK. I'm
also referring you to the renal dietitian for a low-sodium, diabetic-friendly diet plan. Book a
follow-up in four weeks. Any questions?

Patient: Will the new water tablet make me go to the toilet a lot?

Dr. Reyes: Yes, Furosemide is a diuretic, so take it in the morning so it doesn't disturb your
sleep. Avoid taking it in the afternoon or evening.

Patient: Alright, I'll do that. Thank you, doctor.

Dr. Reyes: Take care, Mr. Okonkwo. We'll get those numbers back under control.
""",
    ),
    (
        "Priya Patel — rheumatoid arthritis + GERD + sulfa allergy",
        """
Dr. Huang: Hello Ms. Priya Patel, come in. I'm Dr. Huang. I have your referral notes from your
GP here — you're 41, correct? It says you've been having joint pains for several months now and
your rheumatoid factor came back positive. Tell me in your own words what's been happening.

Patient: Yes, thank you for seeing me. It started about eight months ago. I woke up one morning
and both my hands were so stiff I couldn't make a fist. It was worst in the morning, took about
two hours to ease off. I thought I'd slept funny. But then it kept happening, every morning, and
then I noticed my knuckles were swollen — these joints here — and my wrists too.

Dr. Huang: Morning stiffness lasting more than an hour is a classic feature of inflammatory
arthritis. Has it spread to other joints since then?

Patient: Yes, my feet as well — the balls of my feet hurt when I first stand up. And my right
shoulder has started aching. My GP did blood tests and said the rheumatoid factor was strongly
positive, 84 units, and the anti-CCP was also positive. She referred me straight away.

Dr. Huang: Those results together with your symptoms are very suggestive of rheumatoid arthritis.
How is the pain affecting your daily life? You're 41, so I imagine it's having a significant impact.

Patient: I'm a software engineer, I work at home mostly, which helps. But typing for long periods
is painful. I have to stop and stretch my hands. I'm a mother of two young children, 7 and 9,
and picking things up, opening jars, even fastening my son's school shoes — it's been really
difficult. I've been quite upset about it honestly.

Dr. Huang: That's completely understandable. This is a condition that affects people's whole lives,
not just their joints. What have you been taking for the pain so far?

Patient: Just Naproxen 500mg from my GP when the pain is very bad. It helps a little but upsets
my stomach. I already had GERD before all of this started, so I take Omeprazole 20mg every
morning. The Naproxen still causes heartburn sometimes.

Dr. Huang: Yes, NSAIDs and GERD are a difficult combination. Keep the Omeprazole. Do you have any
known drug allergies?

Patient: Yes, I'm allergic to sulfonamide antibiotics — Bactrim, that kind of thing. I had a
severe rash when I was a teenager, hives all over and my throat was swelling. And I'm also
allergic to Codeine — it makes me violently sick, I vomit uncontrollably.

Dr. Huang: Absolutely noted — sulfonamides and Codeine, both avoided completely. Blood type?

Patient: AB negative. Quite rare apparently.

Dr. Huang: It is. Family history — anyone with autoimmune conditions?

Patient: My mother has lupus. My aunt has psoriasis. So yes, there's definitely something on
that side.

Dr. Huang: That family history is relevant. Autoimmune conditions do cluster in families. Let me
examine you. Starting with your hands. I can see synovitis in the MCPs and PIPs bilaterally —
those joints are warm, tender, with visible swelling. Grip strength reduced, about 60% of normal
on both sides. Wrists have limited flexion and extension. Right shoulder — mildly restricted
range of motion but no significant swelling. Metatarsophalangeal joints tender bilaterally on
squeeze test. No skin rash, no nodules at the elbows. ESR was 68, CRP 22 — both elevated.
X-rays of hands: periarticular osteopenia, no erosions yet, which is good — we've caught this
relatively early.

So yes, I'm confident this is rheumatoid arthritis, seropositive — RF and anti-CCP both positive.
The good news is you don't have erosions yet, which means we have a good window to control this
aggressively with disease-modifying therapy.

I'm starting you on Hydroxychloroquine 400mg once daily. It takes three to six months to show
full effect but has a good safety profile. We'll combine it with Methotrexate 10mg once weekly,
taken on the same day each week, with Folic Acid 5mg daily on all other days to reduce
Methotrexate side effects like mouth ulcers and nausea. You'll need to avoid alcohol on
Methotrexate.

Continue the Naproxen 500mg as needed for flares, keep taking the Omeprazole. I'll also add
Prednisolone 10mg daily as a short bridge while the disease-modifying drugs take effect — we'll
taper that over six weeks.

I'm referring you to our occupational therapist for hand exercises and joint protection strategies.
We'll repeat bloods in four weeks — full blood count, liver function, renal function — as
Methotrexate requires monitoring. Follow-up here in eight weeks. Any questions?

Patient: Is it safe to keep breastfeeding? Oh wait, my youngest is nine now, so no. What about
sun exposure on Hydroxychloroquine?

Dr. Huang: Good question. Hydroxychloroquine can increase sun sensitivity slightly, so use SPF
30 or above. We also need a baseline eye check — very rarely it can affect the retina with
long-term use. I'll refer you to ophthalmology for a baseline assessment.

Patient: Thank you. I feel better knowing there's a treatment plan.

Dr. Huang: You've done the right thing coming in early. We'll keep this under control.
""",
    ),
    (
        "Marcus Thompson — COPD + depression + anxiety + aspirin allergy",
        """
Dr. Osei: Good afternoon, Mr. Marcus Thompson. Please come in and sit down. So we have you here
today for a comprehensive review — you're 54 years old, and I can see from your notes you have
quite a few things we're keeping an eye on. How have you been since I last saw you three months ago?

Patient: Honestly, doctor, up and down. The breathing has been the main issue. I've been using
my blue inhaler a lot more than I should be — probably six to eight times a day sometimes. There
was a particularly bad two weeks in April where I could barely get up the stairs without stopping
halfway. That really frightened me.

Dr. Osei: That kind of worsening is important to explore. Were there any symptoms of infection
during that time — fever, change in the colour or amount of sputum?

Patient: Yes actually. My phlegm went green for about a week and a half. I coughed more than
usual. I ended up going to the urgent care centre and they gave me Amoxicillin and a short course
of Prednisolone. That helped eventually but took about three weeks to fully settle.

Dr. Osei: So that was an acute exacerbation of your COPD, likely infective. Two exacerbations
requiring treatment in the past year, which moves you up on the GOLD severity scale. We had you
at GOLD II — moderate. Are you still smoking?

Patient: I know, I know. I've cut down significantly. I was on thirty a day for years. Now I'm
on about five. My daughter has been on at me. I've been on the patches before but they give me
vivid nightmares. I tried the gum. I just can't seem to fully stop.

Dr. Osei: I hear you — thirty years of smoking is a serious addiction. Cutting from thirty to
five is genuinely meaningful. Let's talk about Varenicline, which works differently from the
patches — it reduces cravings and makes smoking less satisfying. It can also help with your
anxiety in some patients. Something to consider.

Now let's talk about your mental health. You've been on Sertraline 50mg for the depression and
anxiety for about fourteen months. How are you finding it?

Patient: Better than before, definitely. I was in a really dark place last year after my wife
left. I'm not there anymore. But the anxiety is still quite present — I have a lot of health
anxiety specifically, which feeds into the breathing, if that makes sense. When I feel anxious
I feel like I can't breathe, and then I panic because I genuinely can't breathe well, so I'm
never sure which one is causing which.

Dr. Osei: That's an incredibly common and difficult cycle with COPD and anxiety — they amplify
each other. Are you seeing a therapist or doing any talking therapy?

Patient: I was. I had eight sessions of CBT through the NHS. It helped with the thought patterns.
I have a waiting list referral for more but I don't have a date yet.

Dr. Osei: I'll write a chase letter to expedite that referral. Now, you're also on Lorazepam
0.5mg as needed for acute anxiety episodes. How often are you using that?

Patient: Probably twice a week. I know it's a controlled drug. I don't want to become dependent
on it. But when the panic comes on I can't manage without it.

Dr. Osei: That frequency is concerning from a dependency standpoint. Let's discuss adding
Buspirone 5mg twice daily as a non-addictive anxiolytic alongside the Sertraline — it may allow
you to reduce Lorazepam use over time. I'll also increase your Sertraline to 100mg, as 50mg is
often just a starting dose.

Let me ask about your other medications. You're on Salbutamol — the blue rescue inhaler —
and Tiotropium 18 micrograms once daily as your long-acting bronchodilator. Given your
exacerbation history, I want to add a long-acting beta-agonist inhaler, specifically Salmeterol
plus Fluticasone combination inhaler, two puffs twice daily. This combination gives better
control and reduces exacerbation frequency. Make sure to rinse your mouth after each use to
prevent oral thrush.

Do you have any drug allergies we should note?

Patient: Aspirin. I found out the hard way — took it for a headache about fifteen years ago and
my throat closed up. Full anaphylaxis. I carry an EpiPen.

Dr. Osei: Aspirin anaphylaxis is in your notes, yes — I'm highlighting it again today for
emphasis. This means we also need to be very careful with NSAIDs generally, as there can be
cross-reactivity. Ibuprofen, Naproxen — all avoided. Use Paracetamol for pain instead.

Blood type — do you know yours?

Patient: O positive.

Dr. Osei: Thank you. Let me examine you. General: you appear comfortable at rest, not dyspnoeic
at this time. Chest inspection: barrel-shaped, increased AP diameter, consistent with air trapping.
Percussion: hyper-resonant bilaterally. Auscultation: reduced breath sounds throughout, prolonged
expiratory phase, mild end-expiratory wheeze on the right. No crackles today. Heart sounds: dual,
no murmur. BP 128 over 82, HR 76, RR 18 at rest, O2 saturation 94% on room air. Weight 82 kg.

I want to arrange spirometry today to rebaseline your lung function post-exacerbation. I'm also
ordering a full blood count, BNP, ECG, and chest X-ray to make sure there's no cardiac
component to your breathlessness or fluid retention.

Summary of today's changes: add Salmeterol/Fluticasone combination inhaler twice daily, increase
Sertraline to 100mg, add Buspirone 5mg twice daily, discuss Varenicline for smoking cessation.
Continue Tiotropium, Salbutamol PRN, Lorazepam as truly needed. Spirometry today, all blood
results in two weeks, follow up in six weeks.

Do you have any questions for me, Mr. Thompson?

Patient: Will the new inhaler interfere with the anxiety tablets?

Dr. Osei: The Salmeterol can sometimes cause a slight increase in heart rate, which sensitive
people occasionally perceive as anxiety. If that happens, let me know and we can switch to a
different combination. Start with one puff twice daily for the first week, then increase to two.

Patient: And the Lorazepam — should I just stop it?

Dr. Osei: No, never stop Lorazepam suddenly. We'll taper it slowly as the Buspirone takes effect
over four to six weeks. I'll give you a tapering schedule today. Any other questions?

Patient: No, I think that covers it. Thank you, doctor. It means a lot having someone take the
time to go through everything.

Dr. Osei: That's what we're here for. Take care of yourself, Mr. Thompson, and try to get those
last five cigarettes down to zero.
""",
    ),
]


# ── Complex agent queries ─────────────────────────────────────────────────────

COMPLEX_QUERIES = [
    (
        "Multi-condition overlap",
        "Which patients have both diabetes and hypertension?",
    ),
    (
        "Cardiovascular risk clustering",
        "List all patients with cardiovascular risk factors — include smokers, "
        "hypertensives, diabetics, and anyone with a cardiac diagnosis.",
    ),
    (
        "NSAID contraindication cross-check",
        "Which patients should NOT be prescribed NSAIDs like Ibuprofen or Naproxen, "
        "and why? Include both allergy and disease-related contraindications.",
    ),
    (
        "Polypharmacy flag",
        "Which patients are currently taking 4 or more medications? List each patient "
        "and their full medication list.",
    ),
    (
        "Autoimmune and inflammatory conditions",
        "Which patients have been diagnosed with an autoimmune or chronic inflammatory condition?",
    ),
    (
        "Respiratory disease + smoking history",
        "Find all patients with a respiratory diagnosis or active smoking history.",
    ),
    (
        "Penicillin alternatives needed",
        "If I need to prescribe an antibiotic, which patients cannot receive Penicillin "
        "or Sulfonamide antibiotics due to allergies?",
    ),
    (
        "Renal and metabolic monitoring",
        "Which patients need regular renal function or metabolic blood test monitoring, "
        "and what are they being monitored for?",
    ),
    (
        "Age-condition intersection",
        "Which patients over 50 have more than one chronic condition?",
    ),
    (
        "Mental health patients",
        "Which patients have a mental health diagnosis or are on psychiatric medication?",
    ),
]


def main():
    # ── Submit new patients ───────────────────────────────────────────────────
    if not QUERIES_ONLY:
        sep("LOADING 3 NEW PATIENTS")
        new_records = []
        for label, transcript in NEW_PATIENTS:
            print(f"\n  Submitting: {label} …", flush=True)
            resp = post_transcript(transcript)
            new_records.append(resp)
            print(
                f"  → patient_id={resp['patient_id']}  record_id={resp['record_id']}  "
                f"name={resp['patient_name']!r}"
            )
            time.sleep(6)

        print(f"\n  Loaded {len(new_records)} new patient(s).")
    else:
        print("\n  --queries-only: skipping transcript submission.")

    # ── Complex agent queries ─────────────────────────────────────────────────
    sep("COMPLEX MCP AGENT QUERIES (9 patients total)")

    for i, (label, query) in enumerate(COMPLEX_QUERIES, 1):
        print(f"\n  [{i}/{len(COMPLEX_QUERIES)}] {label}")
        print(f"  Query: \"{query}\"")
        result = agent_query(query)
        print(f"\n  Answer:\n{result['answer']}\n")
        print(f"  Patients in response ({len(result['patients'])}):")
        for p in result["patients"]:
            print(f"    • {p['name']} (id={p['id']}, age={p.get('age')})")
        print()
        time.sleep(10)

    sep("DONE")


if __name__ == "__main__":
    main()
