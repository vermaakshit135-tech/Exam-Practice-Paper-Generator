
import os
import json
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


# ==========================================
# PROJECT PATHS
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"

INPUT_FILE = DATA_DIR / "questions.json"
OUTPUT_FILE = DATA_DIR / "llm_analyzer.json"

load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY not found. Please check your .env file."
    )

client = genai.Client(api_key=API_KEY)

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

BATCH_SIZE = 5


# ==========================================
# LOAD QUESTIONS
# ==========================================

def load_questions():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Questions file not found: {INPUT_FILE}"
        )

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    print("Questions loaded successfully!")
    return data


# ==========================================
# COLLECT QUESTIONS
# ==========================================

def collect_questions(data):
    collected = []

    def add_question(year, section, item):
        if not isinstance(item, dict):
            return

        question = item.get("question")

        if question:
            collected.append({
                "year": str(year),
                "section": str(section),
                "question": str(question)
            })

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                add_question(
                    item.get("year", "Unknown"),
                    item.get("section", "Unknown"),
                    item
                )

        return collected

    if not isinstance(data, dict):
        raise ValueError(
            "Unsupported questions.json format."
        )

    for year, sections in data.items():
        if not isinstance(sections, dict):
            continue

        for section, items in sections.items():
            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue

                add_question(year, section, item)

                alternatives = item.get("alternatives", [])

                if isinstance(alternatives, list):
                    for alternative in alternatives:
                        add_question(year, section, alternative)

    return collected


# ==========================================
# GEMINI REQUEST
# ==========================================

def request_gemini(batch, batch_number):
    prompt = f"""
You are an expert AKTU B.Tech academic tutor
for Design and Analysis of Algorithms (DAA).

Analyze and solve the supplied questions.

Return a JSON object with exactly these keys:

{{
  "important_topics": ["topic names"],
  "repeated_questions": [
    {{
      "topic": "topic name",
      "questions": ["original questions"],
      "years": ["available years"]
    }}
  ],
  "topic_distribution": [
    {{
      "topic": "topic name",
      "question_count": 0
    }}
  ],
  "practice_concepts": ["concepts"],
  "answers": [
    {{
      "year": "source year",
      "section": "source section",
      "question": "original question",
      "answer": "complete step-by-step answer",
      "status": "AI-generated; verify before exam use"
    }}
  ]
}}

Rules:
- Answer every supplied question.
- Return one answer entry per supplied question.
- Preserve original question wording, year, and section.
- Explain numerical problems step by step.
- For Master Theorem, identify a, b, f(n), n^(log_b(a)),
  the theorem case, and final time complexity.
- For graph algorithms, show the relevant algorithm steps.
- For theory, provide an exam-style explanation and complexity
  where applicable.
- If essential information is missing, say so explicitly.
- Do not invent missing graph edges, values, or assumptions.
- Mark all answers as AI-generated and requiring verification.
- Do not use Markdown code fences.
- Return valid JSON only.

Questions:
{json.dumps(batch, ensure_ascii=False)}
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
            max_output_tokens=8192
        )
    )

    response_text = response.text

    if not response_text:
        raise ValueError(
            f"Gemini returned an empty response for batch {batch_number}."
        )

    response_text = response_text.strip()

    # First try normal JSON parsing.
    try:
        result = json.loads(response_text)

    except json.JSONDecodeError:
        # Repair invalid backslash escapes such as \{ or \log.
        repaired_text = re.sub(
            r'\\(?!["\\/bfnrtu])',
            r'\\\\',
            response_text
        )

        try:
            result = json.loads(repaired_text)

        except json.JSONDecodeError as error:
            print(f"\nInvalid JSON in batch {batch_number}.")
            print("JSON error:", error)
            print("Response preview:")
            print(response_text[:1500])

            raise ValueError(
                f"Could not parse batch {batch_number}. "
                "Try a smaller batch or check whether Gemini "
                "truncated its response."
            ) from error

    if not isinstance(result, dict):
        raise ValueError(
            f"Batch {batch_number} did not return a JSON object."
        )

    if not isinstance(result.get("answers"), list):
        raise ValueError(
            f"Batch {batch_number} has no valid answers list."
        )

    return result


# ==========================================
# ANALYZE IN SMALL BATCHES
# ==========================================

def analyze_with_gemini(data):
    questions = collect_questions(data)

    if not questions:
        raise ValueError(
            "No questions were found. Check questions.json structure."
        )

    print("Questions found:", len(questions))
    print("Batch size:", BATCH_SIZE)

    all_answers = []
    all_topics = []
    all_repeated = []
    all_distribution = []
    all_concepts = []

    total_batches = (
        len(questions) + BATCH_SIZE - 1
    ) // BATCH_SIZE

    for start in range(0, len(questions), BATCH_SIZE):
        batch_number = start // BATCH_SIZE + 1
        batch = questions[start:start + BATCH_SIZE]

        print(
            f"\nProcessing batch {batch_number}/{total_batches} "
            f"({len(batch)} questions)..."
        )

        result = request_gemini(batch, batch_number)

        # Keep answers associated with their source questions.
        batch_answers = result.get("answers", [])

        for answer_item in batch_answers:
            if isinstance(answer_item, dict):
                answer_item["status"] = (
                    "AI-generated; verify before exam use"
                )
                all_answers.append(answer_item)

        all_topics.extend(
            item for item in result.get("important_topics", [])
            if isinstance(item, str)
        )

        all_repeated.extend(
            result.get("repeated_questions", [])
        )

        all_distribution.extend(
            result.get("topic_distribution", [])
        )

        all_concepts.extend(
            item for item in result.get("practice_concepts", [])
            if isinstance(item, str)
        )

        print("Answers received:", len(batch_answers))

    # Preserve order while removing duplicate topic/concept names.
    all_topics = list(dict.fromkeys(all_topics))
    all_concepts = list(dict.fromkeys(all_concepts))

    final_result = {
        "important_topics": all_topics,
        "repeated_questions": all_repeated,
        "topic_distribution": all_distribution,
        "practice_concepts": all_concepts,
        "answers": all_answers,
        "answer_count": len(all_answers),
        "questions_submitted": len(questions),
        "note": (
            "Answers are AI-generated, not verified official solutions. "
            "Check calculations and algorithms before exam use."
        )
    }

    return final_result


# ==========================================
# SAVE RESULTS
# ==========================================

def save_analysis(result):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    temp_file = OUTPUT_FILE.with_suffix(".tmp")

    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=4
        )

    # Replace the previous output only after all batches succeed.
    temp_file.replace(OUTPUT_FILE)

    print(f"\nAnalysis saved to:\n{OUTPUT_FILE}")


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    try:
        questions_data = load_questions()
        result = analyze_with_gemini(questions_data)

        save_analysis(result)

        print("\n" + "=" * 40)
        print("GEMINI ANALYSIS COMPLETED")
        print("=" * 40)
        print("Questions submitted:", result["questions_submitted"])
        print("Answers generated:", result["answer_count"])

        if result["answer_count"] < result["questions_submitted"]:
            print(
                "WARNING: Some questions have no answer entry. "
                "Review llm_analyzer.json."
            )
        else:
            print("All questions received answer entries.")

        print("\nNext step: update the PDF generator to read")
        print("the 'answers' list from llm_analyzer.json.")

    except Exception as error:
        print("\nERROR:", error)
        raise
