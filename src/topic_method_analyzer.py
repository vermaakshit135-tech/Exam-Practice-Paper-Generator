
import os
import json
from pathlib import Path

from dotenv import load_dotenv
from google import genai


# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"

INPUT_FILE = DATA_DIR / "questions.json"
OUTPUT_FILE = DATA_DIR / "topic_method_analysis.json"


# Gemini configuration
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY not found. Please check your .env file."
    )

client = genai.Client(api_key=api_key)

MODEL = "gemini-3.8-flash"


def load_questions():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Questions file not found: {INPUT_FILE}"
        )

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    all_questions = []

    # Check the actual JSON structure
    if isinstance(data, dict):
        for year, sections in data.items():

            if not isinstance(sections, dict):
                print(f"Skipping unexpected data for: {year}")
                continue

            for section, question_list in sections.items():

                if not isinstance(question_list, list):
                    continue

                for item in question_list:

                    if not isinstance(item, dict):
                        continue

                    # Questions with alternatives
                    if isinstance(item.get("alternatives"), list):
                        for alternative in item["alternatives"]:

                            if (
                                isinstance(alternative, dict)
                                and alternative.get("question")
                            ):
                                all_questions.append({
                                    "year": year,
                                    "section": section,
                                    "question": alternative["question"]
                                })

                    # Normal questions
                    elif item.get("question"):
                        all_questions.append({
                            "year": year,
                            "section": section,
                            "question": item["question"]
                        })

    elif isinstance(data, list):
        # Handle a flat list of questions
        for item in data:
            if isinstance(item, dict) and item.get("question"):
                all_questions.append({
                    "year": item.get("year", "Unknown"),
                    "section": item.get("section", "Unknown"),
                    "question": item["question"]
                })

    print("Input file:", INPUT_FILE)
    print("Questions loaded:", len(all_questions))

    if not all_questions:
        print("Could not find questions in the expected structure.")
        print("Top-level data type:", type(data).__name__)

        if isinstance(data, dict):
            print("Top-level keys:", list(data.keys())[:10])
        elif isinstance(data, list) and data:
            print("First item:", json.dumps(
                data[0],
                ensure_ascii=False,
                indent=2
            ))

    return all_questions


def analyze_with_gemini(questions):
    prompt = f"""
You are an expert AKTU B.Tech exam question analyzer.

Analyze every question and return ONLY valid JSON.

Use this exact structure:

{{
    "analyses": [
        {{
            "question": "original question",
            "year": "year from input",
            "topic": "main topic",
            "subtopic": "specific concept",
            "method": "algorithm or solving method, or Not specified",
            "question_type": "Theory, Algorithm, or Numerical"
        }}
    ]
}}

Rules:
- Analyze every input question.
- Preserve original question wording and year.
- Do not invent information.
- Use "Not specified" when the method is unclear.
- Return one analysis per input question.
- Return valid JSON only.
- Do not use Markdown code fences.

Questions:
{json.dumps(questions, ensure_ascii=False)}
"""

    print("\nSending questions to Gemini...")

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt
    )

    response_text = response.text

    if not response_text:
        raise ValueError("Gemini returned an empty response.")

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as error:
        print("Gemini returned invalid JSON.")
        print("Response preview:", response_text[:1000])
        raise error

    if not isinstance(result, dict) or not isinstance(
        result.get("analyses"), list
    ):
        raise ValueError(
            "Unexpected Gemini response structure. "
            "Expected a JSON object containing an analyses list."
        )

    print("Gemini analysis completed!")
    print("Questions analyzed:", len(result["analyses"]))

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

    print("\nAnalysis saved to:", OUTPUT_FILE)


def main():
    questions = load_questions()

    if not questions:
        print(
            "\nStopping because no questions were loaded. "
            "Check the structure of questions.json."
        )
        return

    try:
        result = analyze_with_gemini(questions)
        save_analysis(result)

    except Exception as error:
        print("\nAnalysis failed.")
        print("Error:", error)
        return

    print("\nAnalysis preview:")
    print(json.dumps(
        result["analyses"][:3],
        ensure_ascii=False,
        indent=4
    ))


if __name__ == "__main__":
    main()
