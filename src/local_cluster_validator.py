
import json
import re
from pathlib import Path
from itertools import combinations

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "processed" / "question_clusters.json"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "local_cluster_review.json"


def normalize(text):
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def classify_cluster(cluster):
    questions = cluster.get("questions", [])
    texts = [q.get("question", "").strip() for q in questions]
    normalized = [normalize(text) for text in texts]

    if len(texts) < 2 or any(len(text) < 20 for text in texts):
        return "REVIEW", "Missing, short, or incomplete question text."

    combined = " ".join(normalized)

    # Similar topic but different algorithms/tasks
    if "single source shortest path" in combined:
        if "dijkstra" in combined and "bellman ford" in combined:
            return "RELATED", "Same SSSP topic, but Dijkstra and Bellman-Ford are different algorithms."

    if "travelling salesman" in combined or " tsp " in f" {combined} ":
        if "dynamic programming" in combined and "branch" in combined:
            return "RELATED", "TSP questions use different methods and input matrices."

    if "set cover" in combined and "vertex cover" in combined:
        return "RELATED", "Set Cover and Vertex Cover are different problems."

    if "randomized algorithm" in combined and (
        "np complete" in combined or "np hard" in combined
    ):
        return "RELATED", "NP-completeness and randomized algorithms are different tasks."

    if "kruskal" in combined and "prim" in combined:
        return "RELATED", "MST questions have different requirements, including algorithm comparison."

    if "red black tree" in combined or "red black" in combined:
        return "RELATED", "Red-Black Tree insertion questions use different key sequences."

    if "approximation algorithm" in combined and (
        "travelling salesman" in combined or "set cover" in combined
        or "vertex cover" in combined
    ):
        return "RELATED", "General approximation questions and problem-specific applications differ."

    # Check whether questions ask the same task
    if all(
        ("backtracking" in text and "branch and bound" in text)
        for text in normalized
    ):
        return "SIMILAR", "Both ask for a comparison of Backtracking and Branch and Bound."

    if all("binomial heap" in text and "union" in text for text in normalized):
        return "SIMILAR", "Both ask about the union operation on Binomial Heaps."

    if all("convex hull" in text for text in normalized):
        return "RELATED", "Same Convex Hull topic, but definition and algorithm/complexity requirements differ."

    if all("master method" in text or "recurrence" in text for text in normalized):
        return "RELATED", "Recurrence questions have different equations; verify OCR and solve separately."

    if all("approximation algorithm" in text for text in normalized):
        return "RELATED", "Same broad topic, but the specific problems may differ."

    if all("red black tree" in text or "red black" in text for text in normalized):
        return "RELATED", "Same data structure, but different input sequences."

    if all("minimum cost spanning tree" in text or "kruskal" in text or "spanning tree" in text for text in normalized):
        return "RELATED", "MST questions overlap but include different requirements."

    if all("travelling salesman" in text or " tsp " in f" {text} " for text in normalized):
        return "RELATED", "Same TSP problem, but methods or input matrices may differ."

    return "REVIEW", "No reliable rule established; manual verification required."


def main():
    if not INPUT_FILE.exists():
        print(f"Input file not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        clusters = json.load(file)

    report = []

    for index, cluster in enumerate(clusters, start=1):
        status, reason = classify_cluster(cluster)

        report.append({
            "cluster_id": cluster.get("cluster_id", index),
            "status": status,
            "reason": reason,
            "questions": cluster.get("questions", [])
        })

        print(
            f"Cluster {cluster.get('cluster_id', index)}: "
            f"{status} - {reason}"
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4, ensure_ascii=False)

    print("\n--- SUMMARY ---")

    for status in ["SIMILAR", "RELATED", "REVIEW"]:
        count = sum(1 for item in report if item["status"] == status)
        print(f"{status}: {count}")

    print(f"\nReport saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
