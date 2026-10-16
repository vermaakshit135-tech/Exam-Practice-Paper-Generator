import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "processed" / "question_clusters.json"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "local_cluster_review.json"


def classify_cluster(cluster):
    questions = cluster.get("questions", [])
    texts = [q.get("question", "").lower() for q in questions]
    combined = " ".join(texts)

    # Incomplete questions
    if any(
        text.strip() in {"solve the recurrence", "solve the following recurrence"}
        for text in texts
    ):
        return "REVIEW", "Incomplete question detected; check original PDF."

    # Clearly unrelated concepts
    unrelated_pairs = [
        ("n queens", "subset sum"),
        ("insertion sort", "skip list"),
        ("binomial tree", "fibonacci heap"),
    ]

    for first, second in unrelated_pairs:
        if first in combined and second in combined:
            return "UNRELATED", f"Different concepts: {first} and {second}."

    # OCR contamination / mixed topics
    if "approximation algorithm" in combined and "recursion tree method" in combined:
        return "UNRELATED", "Possible OCR contamination: recurrence mixed with approximation algorithms."

    # Exact repeated task candidates
    duplicate_clusters = {
        4: "Same Backtracking vs Branch and Bound comparison.",
        14: "Same Binomial Heap union algorithm and complexity question.",
    }

    cluster_id = cluster.get("cluster_id")
    if cluster_id in duplicate_clusters:
        return "DUPLICATE", duplicate_clusters[cluster_id]

    # Related topics but different tasks
    related_clusters = {
        2: "SSSP topic; Dijkstra and Bellman-Ford questions have different requirements.",
        3: "Graph coloring definition versus applications.",
        5: "MST/Kruskal questions include different additional requirements.",
        6: "Red-Black Tree insertion questions use different key sequences.",
        7: "Convex Hull definition versus algorithm and complexity.",
        9: "Recurrence comparison questions need formula/OCR verification.",
        11: "Binomial Heap questions ask about different operations.",
        12: "KMP questions ask for different calculations or explanations.",
        15: "FFT questions have different requirements.",
        18: "TSP questions use different methods and input matrices.",
        19: "Set Cover and Vertex Cover are different problems in a related area.",
    }

    if cluster_id in related_clusters:
        return "RELATED", related_clusters[cluster_id]

    if cluster_id == 1:
        return "REVIEW", "Recurrence equations differ; one question is incomplete."

    if cluster_id == 8:
        return "REVIEW", "Subset Sum questions are related, but N-Queens is unrelated."

    if cluster_id == 10:
        return "REVIEW", "NP-completeness questions are related; randomized algorithms is a different task."

    if cluster_id == 13:
        return "REVIEW", "Mixed topics detected; inspect original PDF for OCR contamination."

    if cluster_id == 16:
        return "UNRELATED", "Binomial Tree and Fibonacci Heap are different structures."

    if cluster_id == 17:
        return "UNRELATED", "Insertion Sort and Skip List are unrelated topics; likely bad grouping."

    return "REVIEW", "Needs manual verification."


def main():
    if not INPUT_FILE.exists():
        print(f"Input file not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        clusters = json.load(file)

    report = []

    for cluster in clusters:
        status, reason = classify_cluster(cluster)

        report.append({
            "cluster_id": cluster.get("cluster_id"),
            "status": status,
            "reason": reason,
            "questions": cluster.get("questions", []),
        })

        print(f"Cluster {cluster.get('cluster_id')}: {status} - {reason}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4, ensure_ascii=False)

    print("\n--- SUMMARY ---")
    for status in ["DUPLICATE", "RELATED", "UNRELATED", "REVIEW"]:
        count = sum(1 for item in report if item["status"] == status)
        print(f"{status}: {count}")

    print(f"\nReport saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()