
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

PROCESSED_DIR = BASE_DIR / "data" / "processed"
INPUT_FILE = PROCESSED_DIR / "question_clusters.json"
OUTPUT_FILE = PROCESSED_DIR / "similar_questions_report.json"


def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def is_complete_question(question):
    text = question.strip()

    if len(text) < 20:
        return False

    if text.lower() == "solve the recurrence":
        return False

    return True


def main():
    clusters = load_json(INPUT_FILE)

    similar_groups = []
    rejected_count = 0

    for cluster in clusters:
        valid_questions = []

        for item in cluster.get("questions", []):
            question_text = item.get("question", "")

            if is_complete_question(question_text):
                valid_questions.append(item)
            else:
                rejected_count += 1

        # A similar group must contain at least 2 questions
        if len(valid_questions) < 2:
            continue

        # Remove exact duplicate entries within this cluster
        unique_questions = []
        seen = set()

        for item in valid_questions:
            key = " ".join(item["question"].lower().split())

            if key not in seen:
                seen.add(key)
                unique_questions.append(item)

        if len(unique_questions) < 2:
            continue

        years = sorted({
            item["year"] for item in unique_questions
        })

        similar_groups.append({
            "cluster_id": cluster.get("cluster_id"),
            "question_count": len(unique_questions),
            "years_appeared": years,
            "year_count": len(years),
            "questions": unique_questions,
            "similarity_scores": cluster.get(
                "similarity_scores", []
            )
        })

    similar_groups.sort(
        key=lambda item: item["year_count"],
        reverse=True
    )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            similar_groups,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("Clusters analyzed:", len(clusters))
    print("Similar question groups:", len(similar_groups))
    print("Short/incomplete entries skipped:", rejected_count)
    print("Report saved to:", OUTPUT_FILE)

    print("\nSimilar question groups:")

    for group in similar_groups:
        print("\nCluster:", group["cluster_id"])
        print("Questions:", group["question_count"])
        print("Different years:", group["year_count"])
        print("Years:", ", ".join(group["years_appeared"]))

        for item in group["questions"]:
            print("-", item["question"])


if __name__ == "__main__":
    main()
