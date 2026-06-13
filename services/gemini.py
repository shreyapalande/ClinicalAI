import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv(override=True)

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

FLASH_MODEL = "gemini-2.5-flash"
EMBED_MODEL = "gemini-embedding-001"

EXTRACTION_PROMPT = """
You are a clinical data extraction assistant. Given a raw doctor-patient conversation transcript,
extract structured medical data and return ONLY valid JSON with this exact schema:

{
  "patient": {
    "name": "string or null",
    "age": number or null,
    "gender": "string or null",
    "contact": "string or null",
    "blood_type": "string or null",
    "allergies": ["list of strings"]
  },
  "visit": {
    "chief_complaint": "string",
    "symptoms": ["list of symptom strings"],
    "diagnoses": ["list of diagnosis strings"],
    "prescriptions": [
      {"drug": "string", "dose": "string", "frequency": "string", "duration": "string"}
    ],
    "vitals": {
      "bp": "string or null",
      "hr": "string or null",
      "temp": "string or null",
      "weight": "string or null",
      "height": "string or null"
    },
    "notes": "string",
    "follow_up": "string or null"
  }
}

Return ONLY the JSON object, no markdown, no explanation.

Transcript:
"""


def extract_record(transcript: str) -> dict:
    response = _client.models.generate_content(
        model=FLASH_MODEL,
        contents=EXTRACTION_PROMPT + transcript,
    )
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def embed_text(text: str) -> list[float]:
    response = _client.models.embed_content(
        model=EMBED_MODEL,
        contents=text,
    )
    return response.embeddings[0].values


def build_visit_text(visit_data: dict) -> str:
    parts = []
    if visit_data.get("chief_complaint"):
        parts.append(f"Chief complaint: {visit_data['chief_complaint']}")
    if visit_data.get("symptoms"):
        parts.append(f"Symptoms: {', '.join(visit_data['symptoms'])}")
    if visit_data.get("diagnoses"):
        parts.append(f"Diagnoses: {', '.join(visit_data['diagnoses'])}")
    if visit_data.get("prescriptions"):
        drugs = [p.get("drug", "") for p in visit_data["prescriptions"]]
        parts.append(f"Medications: {', '.join(drugs)}")
    if visit_data.get("notes"):
        parts.append(f"Notes: {visit_data['notes']}")
    return ". ".join(parts)
