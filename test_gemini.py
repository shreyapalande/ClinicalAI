from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

key = os.getenv("GEMINI_API_KEY")
print(f"Key being used: {key[:8]}...{key[-4:] if key else ''}")
client = genai.Client(api_key=key)

print("=== Testing generate_content ===")
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Say hello and tell me what model you are.",
)
print(response.text)

print("\n=== Testing embed_content ===")
embed_response = client.models.embed_content(
    model="gemini-embedding-001",
    contents="Patient has a headache and fever.",
)
vec = embed_response.embeddings[0].values
print(f"Embedding OK — {len(vec)} dimensions, first 5 values: {vec[:5]}")
