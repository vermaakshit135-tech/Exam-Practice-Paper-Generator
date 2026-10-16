
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "processed" / "question_clusters.json"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "question_classification.json"


def normalize_text(text):
    """Normalize text for basic comparison."""
    text = text.lower()
    text = re.sub(r"\b\d+\s*[a-z]?\.\s*$", "", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def classify_cluster(cluster):
    questions = cluster.get("questions", [])

    if not questions:
        return "REVIEW", "No questions found in this cluster."

    texts = [
        q.get("question", "").strip()
        for q in questions
    ]

    if any(not text for text in texts):
        return "REVIEW", "One or more questions have empty text."

    # Detect OCR contamination or extracted page metadata
    review_signals = [
        "===== page",
        "printed page",
        "roll no",
        "manish kumar",
    ]

    if any(
        signal in text.lower()
        for text in texts
        for signal in review_signals
    ):
        return "REVIEW", "OCR contamination or page metadata detected."

    normalized = [normalize_text(text) for text in texts]

    if len(questions) == 1:
        return "UNIQUE", "Only one question is present in this cluster."

    # Exact repeated questions after normalization
    if len(set(normalized)) == 1:
        return "REPEATED", "Questions match after text normalization."

    combined = " ".join(normalized)

    # Check whether every question contains a shared task phrase.
    # These are candidates, so verify the original questions too.
    repeated_rules = {
        3: ["backtracking", "branch and bound"],
        7: ["union", "binomial heap"],
    }

    cluster_id = cluster.get("cluster_id")

    if cluster_id in repeated_rules:
        required_terms = repeated_rules[cluster_id]

        if all(
            all(term in normalize_text(text) for term in required_terms)
            for text in texts
        ):
            return (
                "REPEATED",
                "Same core task detected by a cluster-specific rule; verify manually."
            )

    # Clearly unrelated pairs/topics
    unrelated_pairs = [
        ("n queens", "subset sum"),
        ("insertion sort", "skip list"),
        ("binomial tree", "fibonacci heap"),
    ]

    for first, second in unrelated_pairs:
        if first in combined and second in combined:
            return "UNRELATED", f"Different concepts detected: {first} and {second}."

    # Cluster 8 is known to contain mixed/OCR-corrupted questions
    if cluster_id == 8:
        return "REVIEW", "Mixed topics or OCR errors may have combined unrelated questions."

    return (
        "SIMILAR",
        "Questions may share a topic but differ in method, input, or requirements."
    )


def main():
    if not INPUT_FILE.exists():
        print(f"Input file not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        clusters = json.load(file)

    results = []

    for cluster in clusters:
        status, reason = classify_cluster(cluster)

        results.append({
            "cluster_id": cluster.get("cluster_id"),
            "classification": status,
            "reason": reason,
            "questions": cluster.get("questions", [])
        })

        print(
            f"Cluster {cluster.get('cluster_id')}: "
            f"{status} - {reason}"
        )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=4, ensure_ascii=False)

    print("\n--- SUMMARY ---")

    for status in ["REPEATED", "SIMILAR", "UNRELATED", "UNIQUE", "REVIEW"]:
        count = sum(
            1 for item in results
            if item["classification"] == status
        )
        print(f"{status}: {count}")

    print(f"\nReport saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
