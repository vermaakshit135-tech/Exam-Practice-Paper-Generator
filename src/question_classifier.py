
import json
import re
from pathlib import Path
from difflib import SequenceMatcher

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"

INPUT_FILE = DATA_DIR / "question_clusters.json"
OUTPUT_FILE = DATA_DIR / "question_classification.json"


def normalize(text):
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def question_text(item):
    if isinstance(item, dict):
        return str(item.get("question", ""))
    return str(item)


def classify_cluster(cluster):
    questions = cluster.get("questions", [])
    texts = [
        normalize(question_text(q))
        for q in questions
        if question_text(q).strip()
    ]

    if len(texts) < 2:
        return "REVIEW", "Not enough readable questions to compare."

    scores = [
        SequenceMatcher(None, texts[i], texts[j]).ratio()
        for i in range(len(texts))
        for j in range(i + 1, len(texts))
    ]

    average_score = sum(scores) / len(scores)

    if average_score >= 0.80:
        return "REPEATED", "Question wording is highly similar."

    return "SIMILAR", (
        "Questions were grouped by the clustering algorithm; "
        "verify that they ask the same concept."
    )


def main():
    if not INPUT_FILE.exists():
        print(f"Input file not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        print("Error: Expected the updated dictionary format.")
        return

    clusters = data.get("clusters", [])
    unclustered = data.get("unclustered_questions", [])

    results = []
    seen = set()

    def add_question(item, classification, cluster_id, reason):
        text = question_text(item).strip()
        key = normalize(text)

        if not key or key in seen:
            return

        seen.add(key)

        results.append({
            "year": item.get("year") if isinstance(item, dict) else None,
            "section": item.get("section") if isinstance(item, dict) else None,
            "question": text,
            "classification": classification,
            "cluster_id": cluster_id,
            "reason": reason
        })

    for cluster in clusters:
        status, reason = classify_cluster(cluster)
        cluster_id = cluster.get("cluster_id")

        for item in cluster.get("questions", []):
            add_question(item, status, cluster_id, reason)

    for item in unclustered:
        add_question(
            item,
            "UNIQUE",
            None,
            "No matching cluster was found."
        )

    counts = {
        label: sum(
            q["classification"] == label for q in results
        )
        for label in ("REPEATED", "SIMILAR", "UNIQUE", "REVIEW")
    }

    output = {
        "total_questions_in_clustering": data.get("total_questions"),
        "total_clusters": len(clusters),
        "classified_questions": len(results),
        "duplicate_texts_skipped": (
            len(clusters) and sum(
                len(c.get("questions", [])) for c in clusters
            ) + len(unclustered) - len(results)
        ),
        "counts": counts,
        "questions": results
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=4, ensure_ascii=False)

    print("\nQUESTION CLASSIFICATION COMPLETED")
    print(f"Questions in clustering file: {data.get('total_questions')}")
    print(f"Questions classified: {len(results)}")
    print(f"Repeated: {counts['REPEATED']}")
    print(f"Similar: {counts['SIMILAR']}")
    print(f"Unique: {counts['UNIQUE']}")
    print(f"Review: {counts['REVIEW']}")
    print(f"Saved to: {OUTPUT_FILE}")

    if len(results) != data.get("total_questions"):
        print(
            "\nWARNING: Classified count differs from total. "
            "Check for duplicate question text or missing entries."
        )


if __name__ == "__main__":
    main()
