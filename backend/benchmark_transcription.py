"""
Benchmarks POST /api/transcription/text end-to-end latency.
Sends 10 clinical transcripts of varying lengths and reports
average, min, max, and standard deviation.

Usage:
    .\\venv\\Scripts\\python backend/benchmark_transcription.py

Optional flag to hit a deployed instance:
    .\\venv\\Scripts\\python backend/benchmark_transcription.py --server=https://your-app.onrender.com
"""

import math
import os
import sys
import time

import requests

SERVER = next(
    (a.split("=", 1)[1] for a in sys.argv if a.startswith("--server=")),
    "http://localhost:8000",
)
URL = f"{SERVER}/api/transcription/text"

# ── 10 transcripts, short → long ─────────────────────────────────────────────

TRANSCRIPTS = [
    # 1 — very short (prescription renewal, ~80 words)
    (
        "Short — prescription renewal",
        "Dr. Adams: Good morning. Quick renewal today — you're here for your blood pressure meds?\n"
        "Patient: Yes, the Amlodipine 5mg. Running low.\n"
        "Dr. Adams: BP today is 128 over 80. Heart rate 70. All good. I'll renew Amlodipine 5mg "
        "for another three months. Any side effects?\n"
        "Patient: None at all.\n"
        "Dr. Adams: Perfect. Come back in three months. Take care.",
    ),
    # 2 — short (~120 words)
    (
        "Short — sore throat",
        "Dr. Singh: Hi Jake, what's going on today?\n"
        "Patient: Sore throat for three days. Mild fever, 100.2. No cough.\n"
        "Dr. Singh: Any difficulty swallowing or ear pain? Jake is 19 years old.\n"
        "Patient: Swallowing is a bit painful. No ear pain.\n"
        "Dr. Singh: Let me take a look. Throat is red, mild exudate on the right tonsil. "
        "Temp 100.4 now. Rapid strep test — let me do that quickly.\n"
        "Patient: Okay.\n"
        "Dr. Singh: Positive. You have strep throat. I'll prescribe Amoxicillin 500mg three "
        "times daily for ten days. Finish the full course. Paracetamol for the fever. "
        "Plenty of fluids. Come back if it gets worse.",
    ),
    # 3 — short-medium (~160 words)
    (
        "Short-medium — UTI",
        "Dr. Patel: Hello Mrs. Carter. What brings you in?\n"
        "Patient: I've had a burning sensation when urinating for about two days. Going more "
        "frequently than usual, maybe every 30 minutes. No fever.\n"
        "Dr. Patel: Any back pain or pain in your sides? Mrs. Carter is 42 years old.\n"
        "Patient: No back pain. Just the lower abdomen feels uncomfortable.\n"
        "Dr. Patel: Any discharge or vaginal symptoms?\n"
        "Patient: No, nothing like that.\n"
        "Dr. Patel: Urine dipstick is positive for nitrites and leucocytes — consistent with "
        "a urinary tract infection. No allergies on your record?\n"
        "Patient: None.\n"
        "Dr. Patel: I'll prescribe Trimethoprim 200mg twice daily for seven days. Drink plenty "
        "of water. Avoid caffeine. If you develop a fever, back pain, or rigors, go to A&E "
        "immediately — that could mean it's moved to the kidneys. Otherwise come back if "
        "symptoms persist after finishing the course.",
    ),
    # 4 — medium (~220 words)
    (
        "Medium — hypertension review",
        "Dr. Hassan: Good afternoon Mr. Brennan. I have your blood results here from last week. "
        "You're 61, here for your annual hypertension review.\n"
        "Patient: Yes. I've been checking my pressure at home — mostly around 148 over 90.\n"
        "Dr. Hassan: That's a bit above target. You're on Lisinopril 10mg. Any cough?\n"
        "Patient: Actually yes, a dry cough for about a month. I thought it was hay fever.\n"
        "Dr. Hassan: That's a known side effect of Lisinopril — it affects about 10 to 15 "
        "percent of patients. We should switch you to an ARB. I'm going to change you to "
        "Losartan 50mg once daily. Same mechanism but no cough side effect.\n"
        "Patient: Good, the cough is quite irritating.\n"
        "Dr. Hassan: Your cholesterol is also slightly elevated — LDL is 3.9. I'd like to "
        "start you on Atorvastatin 20mg at night. Blood results also show your HbA1c is 5.8 "
        "— pre-diabetic range. Not diabetic yet but worth watching. I want you to see our "
        "diabetes prevention nurse for lifestyle advice.\n"
        "Patient: Am I likely to get diabetes?\n"
        "Dr. Hassan: With dietary changes and some weight loss, many people in your position "
        "avoid it entirely. BP today 146 over 92, weight 94kg, BMI 30. Repeat bloods in "
        "three months. Come back in four weeks to check the new medication is working.",
    ),
    # 5 — medium (~260 words)
    (
        "Medium — paediatric asthma",
        "Dr. Obi: Hi Sophie, and hello to mum. Sophie is 8 years old. What's been happening?\n"
        "Parent: She's been waking up at night coughing, maybe three times this week. And "
        "she's been using her blue inhaler before PE at school every day.\n"
        "Dr. Obi: Sophie, does your chest feel tight sometimes?\n"
        "Patient: Yes, like someone is squeezing it. Especially in the morning.\n"
        "Dr. Obi: How long has this been going on?\n"
        "Parent: About six weeks. It started after a cold and never fully settled.\n"
        "Dr. Obi: And she's on Salbutamol — the blue reliever — only at the moment, no "
        "preventer inhaler?\n"
        "Parent: Just the blue one, yes.\n"
        "Dr. Obi: Using reliever inhaler more than three times a week, night symptoms, and "
        "exercise-induced symptoms — Sophie's asthma is not well controlled. We need to step "
        "up her treatment. I'm going to start her on a low-dose inhaled corticosteroid — "
        "Beclomethasone 50 micrograms, two puffs twice daily using a spacer. It's a preventer "
        "that reduces the underlying inflammation. She should use it every day even when she "
        "feels well. Continue the Salbutamol as needed.\n"
        "Parent: Are there side effects?\n"
        "Dr. Obi: At this low dose, very minimal. Rinse her mouth after each use to avoid "
        "a little oral thrush. We'll review in six weeks. Peak flow diary — I'll give you a "
        "chart to fill in twice daily. If she needs her blue inhaler more than every four "
        "hours, bring her to us or A&E. Any allergies?\n"
        "Parent: None known.\n"
        "Dr. Obi: Great. See you in six weeks.",
    ),
    # 6 — medium-long (~310 words)
    (
        "Medium-long — hypothyroidism",
        "Dr. Mensah: Good morning Mrs. Lawson. You're here because your GP found low thyroid "
        "levels on a routine blood test. You're 55 years old. Tell me how you've been feeling.\n"
        "Patient: Exhausted, mainly. I sleep eight hours and still feel tired. I've put on "
        "about 7kg in six months without changing my diet. My hair has been falling out and "
        "my skin feels very dry. I've been constipated as well.\n"
        "Dr. Mensah: All classic symptoms of underactive thyroid. Your TSH came back at 12.4 — "
        "normal is under 4.5. Free T4 is 9.2, which is low. This confirms hypothyroidism.\n"
        "Patient: Is this serious?\n"
        "Dr. Mensah: It's very manageable. We replace the hormone you're not making enough of. "
        "I'm starting you on Levothyroxine 50 micrograms once daily. Take it on an empty "
        "stomach, at least 30 minutes before breakfast. Don't take it with calcium supplements, "
        "iron, or antacids as they reduce absorption.\n"
        "Patient: I take a calcium supplement in the morning.\n"
        "Dr. Mensah: Take the Levothyroxine first thing, then wait an hour before the calcium. "
        "Or move the calcium to the evening. Now, blood type — do you know it?\n"
        "Patient: O positive.\n"
        "Dr. Mensah: Any allergies?\n"
        "Patient: Penicillin — gives me a rash.\n"
        "Dr. Mensah: Noted. We'll repeat TSH and free T4 in eight weeks. It usually takes "
        "six to eight weeks for levels to stabilise at a new dose. You should start feeling "
        "better within four to six weeks — energy first, then weight and hair. Weight 78kg, "
        "BP 118 over 74, HR 58 — slightly slow which is consistent with the hypothyroidism, "
        "should improve on treatment. Any questions?\n"
        "Patient: Will I be on this forever?\n"
        "Dr. Mensah: Most people with hypothyroidism take Levothyroxine lifelong, yes. But "
        "the dose can vary and we'll monitor it annually. It's a simple daily tablet with "
        "no significant side effects at the right dose. See you in eight weeks.",
    ),
    # 7 — long (~380 words)
    (
        "Long — new onset type 2 diabetes",
        "Dr. Reyes: Good afternoon Mr. Nkomo. I'm Dr. Reyes. Your GP has referred you because "
        "your blood sugar has come back very high. You're 49 years old. Tell me what's been "
        "going on.\n"
        "Patient: I've been incredibly thirsty for months. Drinking maybe three litres of water "
        "a day and still thirsty. Going to the toilet constantly, including twice at night. "
        "I've lost about 5kg without trying. And I've been blurry-eyed — I thought I needed "
        "new glasses.\n"
        "Dr. Reyes: Those are all significant symptoms. The blurry vision with high blood sugar "
        "is osmotic — it affects the lens of the eye temporarily. Your fasting glucose from "
        "the GP was 14.2 and your HbA1c is 10.1. That is well into the diabetic range. This "
        "is a new diagnosis of Type 2 Diabetes Mellitus.\n"
        "Patient: I was afraid of that. My father had diabetes.\n"
        "Dr. Reyes: Family history is a risk factor, yes. But this is very manageable. We're "
        "going to start treatment today. I'm going to prescribe Metformin 500mg twice daily "
        "with meals for the first month to let your stomach adjust, then increase to 1000mg "
        "twice daily. Metformin is our first-line medication — it's been used for 60 years, "
        "very safe, and has good evidence.\n"
        "Patient: Any side effects?\n"
        "Dr. Reyes: GI side effects — nausea, loose stool — are common in the first few weeks. "
        "Always take it with food. If severe, call us. Rare but important: avoid it if you're "
        "having contrast dye for a scan — let any doctor know you're on Metformin.\n"
        "Patient: What about diet?\n"
        "Dr. Reyes: Big impact. Reduce refined carbohydrates — white bread, white rice, sugary "
        "drinks. I'm referring you to our diabetes dietitian and the structured education "
        "programme — DESMOND — which runs over two days. Very valuable.\n"
        "Patient: Okay. What about the blurry vision?\n"
        "Dr. Reyes: As blood sugar comes down the vision usually clears. I'm also referring "
        "you for a diabetic eye screening — annual from now. And diabetic foot check. "
        "Examination today: weight 102kg, BMI 33, BP 142 over 88 — we'll need to address "
        "that too in time. Blood type?\n"
        "Patient: B negative.\n"
        "Dr. Reyes: Any drug allergies?\n"
        "Patient: None known.\n"
        "Dr. Reyes: Good. HbA1c, renal function, and liver function in three months. "
        "I want to see you in four weeks. Bring your home glucose readings — I'll give you "
        "a glucometer and show you how to use it today. Do you have any other questions?\n"
        "Patient: Will I need insulin eventually?\n"
        "Dr. Reyes: Not necessarily. Many people manage well on tablets and lifestyle alone. "
        "We cross that bridge if and when we reach it. Focus on the diet changes first — "
        "they can make a dramatic difference. See you in four weeks.",
    ),
    # 8 — long (~420 words)
    (
        "Long — chest pain work-up",
        "Dr. Osei: Mr. Flynn, I'm Dr. Osei. You've been brought in by ambulance with chest "
        "pain. Tell me exactly what happened.\n"
        "Patient: I was walking up the stairs at work — just a normal staircase — and I got "
        "this crushing pressure right in the middle of my chest. Like an elephant sitting on "
        "me. It went into my left arm and up into my jaw. I had to stop. It lasted about "
        "10 minutes and then eased off when I sat down.\n"
        "Dr. Osei: Did you have any sweating, nausea, or feel like you were going to faint?\n"
        "Patient: Yes, sweating, and I felt sick. I nearly vomited.\n"
        "Dr. Osei: Has this happened before?\n"
        "Patient: Once three weeks ago, but milder. I thought it was indigestion.\n"
        "Dr. Osei: How old are you and do you smoke?\n"
        "Patient: 63. I smoked for 30 years, stopped five years ago. I have high cholesterol — "
        "I'm on Atorvastatin 40mg. My father had a heart attack at 58.\n"
        "Dr. Osei: Any allergies?\n"
        "Patient: Codeine. Makes me very confused and drowsy.\n"
        "Dr. Osei: Blood type?\n"
        "Patient: A positive.\n"
        "Dr. Osei: Mr. Flynn is 63 years old. ECG shows ST depression in leads V4 to V6 "
        "and lateral leads — that is concerning for myocardial ischaemia. Troponin I is "
        "elevated at 0.08 — above our threshold of 0.04. BP 158 over 96, HR 92, RR 18, "
        "O2 sats 97% on room air. I'm diagnosing this as a Non-ST Elevation Myocardial "
        "Infarction — NSTEMI.\n"
        "Patient: Am I having a heart attack?\n"
        "Dr. Osei: You've had what we call a heart attack, yes — a partial blockage. The "
        "good news is you're in the right place and we caught it. I'm starting treatment "
        "immediately. Aspirin 300mg loading dose right now, then 75mg daily. Ticagrelor "
        "180mg loading dose — a second antiplatelet. Fondaparinux anticoagulant injection. "
        "Metoprolol 25mg to slow the heart and reduce oxygen demand. GTN spray under the "
        "tongue if the pain returns.\n"
        "Patient: What happens next?\n"
        "Dr. Osei: You'll be admitted to the cardiac care unit. The cardiology team will "
        "do a coronary angiogram — likely tomorrow morning — to look at the arteries and "
        "decide if you need a stent or bypass surgery. I need you to be nil by mouth from "
        "midnight in case of a procedure. I'm also giving you a statin boost — switching "
        "Atorvastatin to 80mg tonight. Do you have any questions?\n"
        "Patient: How serious is this?\n"
        "Dr. Osei: Serious, but treatable. Many people make a full recovery after a stent. "
        "We're moving fast to protect your heart muscle. Your family has been called?",
    ),
    # 9 — very long (~480 words)
    (
        "Very long — complex multimorbidity review",
        "Dr. Chen: Good morning Mr. Petrov. You're 72 years old and we have quite a lot to "
        "go through today — your annual multimorbidity review. How have you been overall?\n"
        "Patient: Mixed, doctor. The left knee has been very painful — I can barely walk to "
        "the shops. The breathlessness has been better since you adjusted the diuretic. "
        "My mood has been low since my wife passed in February.\n"
        "Dr. Chen: I'm very sorry about your wife. Grief can have real physical effects too. "
        "Let's go through each problem systematically. Starting with the heart failure — "
        "you're on Bisoprolol 5mg, Ramipril 10mg, and Spironolactone 25mg. The Furosemide "
        "we increased to 80mg last month. Are you weighing yourself daily?\n"
        "Patient: Yes. Weight has been stable, about 78kg. Ankles not swollen anymore.\n"
        "Dr. Chen: Excellent. BNP from last week is 280 — down from 420 three months ago. "
        "That's a meaningful improvement in the heart failure. Kidney function — creatinine "
        "is 1.4, eGFR 52. Potassium 4.6 — fine with the Spironolactone.\n"
        "Now the knee — you have established osteoarthritis of the left knee, confirmed on "
        "X-ray. You've tried Paracetamol?\n"
        "Patient: Not helping much. Can I take Ibuprofen?\n"
        "Dr. Chen: No — with heart failure and your kidney function, NSAIDs are contraindicated. "
        "They retain fluid, worsen heart failure, and can damage the kidneys. I want to refer "
        "you to the orthopaedic team. At 72 with this severity, a knee replacement may be "
        "the best option. In the meantime, I'll add Capsaicin cream topically. Physiotherapy "
        "for knee strengthening would also help.\n"
        "Patient: What about the mood?\n"
        "Dr. Chen: Bereavement is not automatically depression, but if it's affecting your "
        "daily life after six months, we should treat it. I want to refer you to the grief "
        "counselling service first. If your mood hasn't lifted in six weeks, we'll consider "
        "an antidepressant — but carefully, as some interact with your heart medications.\n"
        "Patient: I'm also having trouble sleeping.\n"
        "Dr. Chen: Related to the grief and low mood most likely. Avoid sleeping tablets — "
        "they increase fall risk at your age. Sleep hygiene advice: fixed wake time, no "
        "screens after 9pm, no caffeine after noon. The counselling may help with that too.\n"
        "Now, your Type 2 Diabetes — HbA1c is 7.2, which is acceptable for your age. "
        "Metformin 1000mg twice daily, continuing. Diabetic eye screening done last month "
        "— mild background retinopathy, no treatment needed yet, annual review.\n"
        "Atrial fibrillation — rate 74 on the Bisoprolol, well controlled. You're on "
        "Apixaban 5mg twice daily for stroke prevention. Continue that — never stop it "
        "without discussing with us first.\n"
        "Blood type A negative. No known drug allergies. BP today 126 over 74 — good. "
        "Weight 78kg stable. I'm making referrals today to orthopaedics, grief counselling, "
        "and physiotherapy. Repeat bloods in three months. Anything else worrying you?\n"
        "Patient: No, I think that covers everything. Thank you for your time.\n"
        "Dr. Chen: Of course. Take care of yourself, Mr. Petrov. See you in three months.",
    ),
    # 10 — longest (~540 words)
    (
        "Longest — new patient comprehensive intake",
        "Dr. Williams: Good morning. I'm Dr. Williams. You're a new patient registering with "
        "our practice today — this is a comprehensive new patient assessment. Your name?\n"
        "Patient: Fatima Al-Rashid.\n"
        "Dr. Williams: Age?\n"
        "Patient: 38.\n"
        "Dr. Williams: Thank you. And what's brought you in today aside from registration — "
        "any active concerns?\n"
        "Patient: A few things. I've had recurring headaches for about six months. Almost "
        "daily. Mostly at the front and behind my eyes. And I've been feeling very tired, "
        "not sleeping well.\n"
        "Dr. Williams: Tell me more about the headaches. Are they throbbing or pressure-like? "
        "Any nausea, light sensitivity, or visual changes?\n"
        "Patient: Pressure. Like a band around my head. Worse by the end of the day. No "
        "nausea. No visual changes. Paracetamol helps a bit.\n"
        "Dr. Williams: How many days a week are you taking Paracetamol for them?\n"
        "Patient: Maybe four or five days.\n"
        "Dr. Williams: That frequency is important — taking painkillers more than three days "
        "a week can actually cause what we call medication overuse headache, which then "
        "requires the painkiller more and more. The pattern you're describing sounds like "
        "tension-type headache, possibly compounded by medication overuse.\n"
        "Patient: I had no idea. What should I do?\n"
        "Dr. Williams: We'll talk through that. Tell me about the sleep first.\n"
        "Patient: I lie in bed for an hour before I fall asleep. Wake up two or three times. "
        "Mind racing — I'm a project manager, quite a stressful job.\n"
        "Dr. Williams: Any low mood, anxiety, or panic attacks?\n"
        "Patient: Anxiety, yes. Mostly work-related. No panic attacks as such, but I feel "
        "on edge a lot. My GP back home prescribed me Sertraline 50mg about a year ago "
        "but I stopped it after four months because I felt better.\n"
        "Dr. Williams: Past medical history?\n"
        "Patient: Asthma as a child — haven't needed an inhaler since I was about 14. "
        "Iron deficiency anaemia diagnosed last year — I was taking Ferrous Sulphate but "
        "I finished the course.\n"
        "Dr. Williams: Surgical history?\n"
        "Patient: Appendectomy at 22. Caesarean section three years ago for my youngest.\n"
        "Dr. Williams: Family history?\n"
        "Patient: Mother has type 2 diabetes and hypertension. Father had a stroke at 64. "
        "Older brother has depression.\n"
        "Dr. Williams: Drug allergies?\n"
        "Patient: Amoxicillin — causes a red rash all over. Not sure if it's a true allergy "
        "or intolerance but I avoid all Penicillin.\n"
        "Dr. Williams: Noted — Penicillin allergy documented. Blood type?\n"
        "Patient: AB positive.\n"
        "Dr. Williams: Examination — BP 122 over 78, HR 76, weight 64kg, height 163cm, BMI "
        "24.1. No focal neurological signs. Cervical and trapezius muscles quite tender "
        "on palpation — consistent with tension headache from postural and stress factors.\n"
        "My plan today: For headaches — I want you to keep a headache diary for four weeks "
        "and cut the Paracetamol to no more than two days a week. If the headaches don't "
        "improve, we can try Amitriptyline 10mg at night as a preventative — it also helps "
        "with sleep. For the sleep and anxiety — I'm referring you to the IAPT service for "
        "CBT. We'll hold off on restarting Sertraline unless the CBT doesn't help. For "
        "anaemia — I want a repeat full blood count and ferritin today. If iron is low "
        "again, we'll restart Ferrous Sulphate 200mg twice daily.\n"
        "Patient: Is there anything I can do today for the tension headaches?\n"
        "Dr. Williams: Yes — neck stretches, posture awareness at your desk, and a short "
        "walk at lunchtime. Heat on the neck and shoulders can help. And try to cut back on "
        "caffeine gradually — sudden withdrawal itself causes headaches.\n"
        "Patient: Thank you. This has been really helpful.\n"
        "Dr. Williams: We're glad to have you with the practice. I'll send referrals to IAPT "
        "today. Book in for the blood test at reception. Follow up with me in four weeks.",
    ),
]


# ── Benchmark ─────────────────────────────────────────────────────────────────

def run():
    print(f"\nTarget: {URL}")
    print(f"Sending {len(TRANSCRIPTS)} transcripts...\n")
    print(f"{'#':<4} {'Label':<42} {'Words':>6} {'Latency':>10}")
    print("─" * 68)

    latencies = []

    for i, (label, transcript) in enumerate(TRANSCRIPTS, 1):
        word_count = len(transcript.split())
        try:
            t0 = time.perf_counter()
            r = requests.post(URL, data={"transcript": transcript}, timeout=120)
            elapsed = time.perf_counter() - t0

            if r.status_code == 200:
                latencies.append(elapsed)
                print(f"{i:<4} {label:<42} {word_count:>6} {elapsed:>9.2f}s")
            else:
                print(f"{i:<4} {label:<42} {word_count:>6} {'ERROR '+str(r.status_code):>10}")
        except requests.exceptions.Timeout:
            print(f"{i:<4} {label:<42} {word_count:>6} {'TIMEOUT':>10}")
        except requests.exceptions.ConnectionError:
            print(f"{i:<4} {label:<42} {word_count:>6} {'NO SERVER':>10}")

    if not latencies:
        print("\nNo successful requests — is the server running?")
        return

    n = len(latencies)
    avg = sum(latencies) / n
    mn = min(latencies)
    mx = max(latencies)
    variance = sum((x - avg) ** 2 for x in latencies) / n
    std = math.sqrt(variance)

    print("\n" + "─" * 68)
    print(f"  Requests completed : {n}/{len(TRANSCRIPTS)}")
    print(f"  Average latency    : {avg:.2f}s")
    print(f"  Min                : {mn:.2f}s")
    print(f"  Max                : {mx:.2f}s")
    print(f"  Std deviation      : {std:.2f}s")
    print()


if __name__ == "__main__":
    run()
