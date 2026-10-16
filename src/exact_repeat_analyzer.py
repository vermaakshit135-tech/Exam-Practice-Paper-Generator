
import json
import re
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

PROCESSED_DIR = BASE_DIR / "data" / "processed"
INPUT_FILE = PROCESSED_DIR / "validated_questions.json"
OUTPUT_FILE = PROCESSED_DIR / "exact_repeated_questions.json"


def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def normalize_question(question):
    question = question.lower()
    question = re.sub(r"[^\w\s]", " ", question)
    question = re.sub(r"\s+", " ", question)
    return question.strip()


def main():
    questions = load_json(INPUT_FILE)

    question_groups = defaultdict(list)

    for item in questions:
        question_text = item.get("question", "")
        normalized = normalize_question(question_text)

        if normalized:
            question_groups[normalized].append(item)

    repeated_questions = []

    for normalized, items in question_groups.items():
        if len(items) > 1:
            repeated_questions.append({
                "question": items[0]["question"],
                "frequency": len(items),
                "years": sorted(set(
                    item["year"] for item in items
                )),
                "occurrences": items
            })

    repeated_questions.sort(
        key=lambda item: item["frequency"],
        reverse=True
    )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            repeated_questions,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("Total questions analyzed:", len(questions))
    print("Exact repeated question groups:", len(repeated_questions))
    print("Saved to:", OUTPUT_FILE)

    print("\nTop repeated questions:")

    for item in repeated_questions[:10]:
        print("\nQuestion:", item["question"])
        print("Frequency:", item["frequency"])
        print("Years:", ", ".join(item["years"]))


if __name__ == "__main__":
    main()
