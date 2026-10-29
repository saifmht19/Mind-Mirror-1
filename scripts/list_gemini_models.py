"""List Gemini models available to the configured key (useful when choosing GEMINI_MODEL)."""
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

for model in client.models.list():
    if "generateContent" in (model.supported_actions or []):
        print(model.name)