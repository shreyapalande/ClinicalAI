import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv(override=True)


def _load_key_pool() -> list[str]:
    """Collect all GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3, … from env."""
    keys = []
    primary = os.getenv("GEMINI_API_KEY", "").strip()
    if primary:
        keys.append(primary)
    i = 2
    while True:
        k = os.getenv(f"GEMINI_API_KEY_{i}", "").strip()
        if not k:
            break
        keys.append(k)
        i += 1
    if not keys:
        raise RuntimeError("No GEMINI_API_KEY found in environment.")
    return keys


class _KeyPool:
    """Round-robin Gemini client pool — rotates on 429 / RESOURCE_EXHAUSTED."""

    def __init__(self, keys: list[str]):
        self._keys = keys
        self._idx = 0
        self._client = genai.Client(api_key=keys[0])
        print(f"[gemini] loaded {len(keys)} API key(s).", flush=True)

    def _rotate(self) -> None:
        self._idx = (self._idx + 1) % len(self._keys)
        self._client = genai.Client(api_key=self._keys[self._idx])
        print(f"[gemini] rotated to key {self._idx + 1}/{len(self._keys)}.", flush=True)

    def call(self, fn, *args, **kwargs):
        """Call fn(client, *args, **kwargs), rotating through keys on rate-limit errors."""
        import time
        start = self._idx
        while True:
            try:
                return fn(self._client, *args, **kwargs)
            except Exception as e:
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    self._rotate()
                    if self._idx == start:
                        raise RuntimeError("All Gemini API keys exhausted.") from e
                    # Brief pause so per-minute limits on the next key have time to clear
                    time.sleep(2)
                else:
                    raise


_pool = _KeyPool(_load_key_pool())

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
    def _call(client):
        return client.models.generate_content(
            model=FLASH_MODEL,
            contents=EXTRACTION_PROMPT + transcript,
        )
    response = _pool.call(_call)
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def embed_text(text: str) -> list[float]:
    def _call(client):
        return client.models.embed_content(
            model=EMBED_MODEL,
            contents=text,
        )
    response = _pool.call(_call)
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
