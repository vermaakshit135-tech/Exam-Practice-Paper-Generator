
import json
from pathlib import Path
from itertools import combinations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "processed" / "questions.json"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "question_clusters.json"

SIMILARITY_THRESHOLD = 0.45


# ============================================================
# LOAD QUESTIONS
# ============================================================

def load_questions():
    """Load extracted questions from JSON."""

    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Questions file not found: {INPUT_FILE}")

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    print("Questions JSON loaded successfully!")
    return data


# ============================================================
# EXTRACT QUESTIONS
# ============================================================

def extract_questions(data):
    """Extract questions from all years and sections."""

    extracted = []

    def add_question(item, year, section):
        if not isinstance(item, dict):
            return

        question = item.get("question")

        if isinstance(question, str) and question.strip():
            extracted.append({
                "year": year,
                "section": section,
                "question": question.strip()
            })

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                add_question(
                    item,
                    item.get("year", "Unknown"),
                    item.get("section", "Unknown")
                )

    elif isinstance(data, dict):
        for year, sections in data.items():
            if not isinstance(sections, dict):
                continue

            for section_name, section_data in sections.items():
                if not isinstance(section_data, list):
                    continue

                for item in section_data:
                    if not isinstance(item, dict):
                        continue

                    # Section C alternatives
                    if section_name == "section_c":
                        alternatives = item.get("alternatives", [])

                        if isinstance(alternatives, list):
                            for alternative in alternatives:
                                add_question(
                                    alternative, year, section_name
                                )
                    else:
                        add_question(item, year, section_name)

    print(f"Total extracted questions: {len(extracted)}")
    return extracted


# ============================================================
# CLUSTER QUESTIONS
# ============================================================

def cluster_questions(questions):
    """
    Group questions conservatively.
    A question must meet the threshold against every group member.
    Return both clusters and unclustered question indices.
    """

    if len(questions) < 2:
        return [], list(range(len(questions)))

    texts = [item["question"] for item in questions]

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True
    )

    try:
        vectors = vectorizer.fit_transform(texts)
    except ValueError as error:
        print("Clustering could not be completed:", error)
        return [], list(range(len(questions)))

    similarity_matrix = cosine_similarity(vectors)
    groups = []

    for i in range(len(questions)):
        best_group = None
        best_score = -1.0

        for group in groups:
            scores = [
                float(similarity_matrix[i, member])
                for member in group
            ]

            if all(score >= SIMILARITY_THRESHOLD for score in scores):
                group_score = min(scores)

                if group_score > best_score:
                    best_score = group_score
                    best_group = group

        if best_group is not None:
            best_group.append(i)
        else:
            groups.append([i])

    clusters = []
    clustered_indices = set()

    for group in groups:
        if len(group) < 2:
            continue

        similarity_scores = []

        for i, j in combinations(group, 2):
            similarity_scores.append({
                "question_1": questions[i]["question"],
                "question_2": questions[j]["question"],
                "score": round(float(similarity_matrix[i, j]), 3)
            })

        clusters.append({
            "cluster_id": len(clusters) + 1,
            "questions": [
                questions[index] for index in group
            ],
            "similarity_scores": similarity_scores
        })

        clustered_indices.update(group)

    unclustered_indices = [
        index
        for index in range(len(questions))
        if index not in clustered_indices
    ]

    return clusters, unclustered_indices


# ============================================================
# SAVE RESULTS
# ============================================================

def save_results(clusters, questions, unclustered_indices):
    """Save clusters and unclustered questions in one JSON object."""

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "similarity_threshold": SIMILARITY_THRESHOLD,
        "total_questions": len(questions),
        "total_clusters": len(clusters),
        "clusters": clusters,
        "unclustered_questions": [
            questions[index] for index in unclustered_indices
        ]
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=4)

    print(f"Results saved to: {OUTPUT_FILE}")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("QUESTION CLUSTERING")
    print("=" * 60)

    data = load_questions()
    questions = extract_questions(data)

    if not questions:
        print("No questions found. Check questions.json.")
        return

    clusters, unclustered_indices = cluster_questions(questions)

    save_results(clusters, questions, unclustered_indices)

    clustered_count = sum(
        len(cluster["questions"])
        for cluster in clusters
    )

    print(f"\nQuestions processed: {len(questions)}")
    print(f"Similar-question groups found: {len(clusters)}")
    print(f"Questions included in groups: {clustered_count}")
    print(f"Questions not included in groups: {len(unclustered_indices)}")

    print("\nCLUSTER SUMMARY")
    print("-" * 60)

    for cluster in clusters:
        print(
            f"\nCluster {cluster['cluster_id']}: "
            f"{len(cluster['questions'])} questions"
        )

        for item in cluster["questions"]:
            print(
                f"  [{item['year']}] "
                f"{item['question'][:150]}"
            )

    print("\nClustering completed!")


if __name__ == "__main__":
    main()
