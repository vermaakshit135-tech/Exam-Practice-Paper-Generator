
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

PROCESSED_DIR = BASE_DIR / "data" / "processed"
QUESTIONS_FILE = PROCESSED_DIR / "generated_paper.json"
OUTPUT_FILE = PROCESSED_DIR / "validated_questions.json"


def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def main():
    questions = load_json(QUESTIONS_FILE)

    valid_questions = []
    rejected_questions = []

    for item in questions:
        question_text = item.get("question", "").strip()

        if len(question_text) < 15:
            rejected_questions.append({
                **item,
                "rejection_reason": "Question is too short or incomplete"
            })
            continue

        valid_questions.append(item)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            valid_questions,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("Total questions:", len(questions))
    print("Valid questions:", len(valid_questions))
    print("Rejected questions:", len(rejected_questions))
    print("Saved to:", OUTPUT_FILE)

    if rejected_questions:
        print("\nRejected question examples:")
        for item in rejected_questions[:5]:
            print("-", item["question"])


if __name__ == "__main__":
    main()
