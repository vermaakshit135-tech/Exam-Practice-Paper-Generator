
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

for model in ["gemini-2.5-flash", "gemini-3.5-flash-lite"]:
    try:
        response = client.models.generate_content(
            model=model,
            contents="Reply with only the word OK."
        )
        print(f"{model}: SUCCESS - {response.text}")
    except Exception as e:
        print(f"{model}: FAILED - {e}")
