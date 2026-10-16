import os
import json
from pathlib import Path
from dotenv import load_dotenv
from google import genai

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data" / "processed"

INPUT_FILE = DATA_DIR / "questions.json"
OUTPUT_FILE = DATA_DIR / "llm_analyzer.json"

# Load environment variables
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY not found. Please check your .env file."
    )

# Gemini client
client = genai.Client(api_key=api_key)

MODEL = "gemini-3.8-flash"


def load_questions():
    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        questions = json.load(file)

    print("Questions loaded successfully!")

    return questions


def analyze_with_gemini(questions):

    prompt = f"""
You are an expert academic question paper analyzer
for AKTU B.Tech exams.

Analyze the following previous-year questions.

Return ONLY a valid JSON object.
Do not use Markdown code fences.
Do not add explanations outside the JSON.

Use exactly these four keys:

{{
    "important_topics": [],
    "repeated_questions": [
        {{
            "topic": "topic name",
            "questions": ["original question"],
            "years": ["year if available"]
        }}
    ],
    "topic_distribution": [
        {{
            "topic": "topic name",
            "question_count": 0
        }}
    ],
    "practice_concepts": []
}}

Rules:
- Do not invent questions or years.
- Preserve original question wording as much as possible.
- Group conceptually similar questions.
- Do not invent question counts.
- Use empty lists when information is unavailable.
- Return valid JSON only.

Questions data:
{json.dumps(questions, ensure_ascii=False, indent=2)}
"""

    # Send prompt to Gemini
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt
    )

    # Check Gemini response
    response_text = response.text

    if not response_text:
        raise ValueError(
            "Gemini returned an empty response. Please try again."
        )

    print("\nGemini response received successfully!")

    # Convert JSON text into a Python dictionary
    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as error:
        print("Gemini did not return valid JSON.")
        print("Raw response:", response_text)
        raise error

    return result


def save_analysis(result):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=4
        )

    print(f"\nAnalysis saved to: {OUTPUT_FILE}")


if __name__ == "__main__":

    questions = load_questions()

    result = analyze_with_gemini(questions)

    print("\nGEMINI ANALYSIS")
    print("-" * 40)
    print(json.dumps(result, ensure_ascii=False, indent=4))

    save_analysis(result)
