
import json
from pathlib import Path
from itertools import combinations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    BASE_DIR / "data" / "processed" / "questions.json"
)

OUTPUT_FILE = (
    BASE_DIR / "data" / "processed" / "question_clusters.json"
)

SIMILARITY_THRESHOLD = 0.45


# ============================================================
# LOAD QUESTIONS
# ============================================================

def load_questions():
    """Load extracted questions from JSON."""

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Questions file not found: {INPUT_FILE}"
        )

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

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue

            question = item.get("question")

            if question and question.strip():
                extracted.append({
                    "year": item.get("year", "Unknown"),
                    "section": item.get("section", "Unknown"),
                    "question": question.strip()
                })

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

                    # Section C: process alternatives separately
                    if section_name == "section_c":
                        alternatives = item.get("alternatives", [])

                        for alternative in alternatives:
                            if not isinstance(alternative, dict):
                                continue

                            question = alternative.get("question")

                            if question and question.strip():
                                extracted.append({
                                    "year": year,
                                    "section": section_name,
                                    "question": question.strip()
                                })

                    # Sections A and B
                    else:
                        question = item.get("question")

                        if question and question.strip():
                            extracted.append({
                                "year": year,
                                "section": section_name,
                                "question": question.strip()
                            })

    print(f"Total extracted questions: {len(extracted)}")

    return extracted


# ============================================================
# CLUSTER QUESTIONS
# ============================================================

def cluster_questions(questions):
    """
    Group questions conservatively.

    A question joins a group only when it meets the similarity
    threshold against every question already in that group.
    This reduces incorrect grouping caused by transitive links.
    """

    if len(questions) < 2:
        return []

    texts = [item["question"] for item in questions]

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True
    )

    vectors = vectorizer.fit_transform(texts)

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

            # Must be sufficiently similar to every group member
            if all(
                score >= SIMILARITY_THRESHOLD
                for score in scores
            ):
                group_score = min(scores)

                if group_score > best_score:
                    best_score = group_score
                    best_group = group

        if best_group is not None:
            best_group.append(i)
        else:
            groups.append([i])

    clusters = []

    for group in groups:

        # Ignore questions without a sufficiently similar partner
        if len(group) < 2:
            continue

        similarity_scores = []

        for i, j in combinations(group, 2):

            score = float(similarity_matrix[i, j])

            similarity_scores.append({
                "question_1": questions[i]["question"],
                "question_2": questions[j]["question"],
                "score": round(score, 3)
            })

        clusters.append({
            "cluster_id": len(clusters) + 1,
            "questions": [
                questions[index] for index in group
            ],
            "similarity_scores": similarity_scores
        })

    return clusters


# ============================================================
# SAVE CLUSTERS
# ============================================================

def save_clusters(clusters):
    """Save similar-question groups to JSON."""

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            clusters,
            file,
            ensure_ascii=False,
            indent=4
        )

    print(f"Clusters saved to: {OUTPUT_FILE}")


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

    try:
        clusters = cluster_questions(questions)

    except ValueError as error:
        print("Clustering could not be completed:", error)
        return

    save_clusters(clusters)

    print(f"\nQuestions processed: {len(questions)}")
    print(f"Similar-question groups found: {len(clusters)}")

    clustered_count = sum(
        len(cluster["questions"])
        for cluster in clusters
    )

    print(f"Questions included in groups: {clustered_count}")
    print(
        "Questions not included in groups:",
        len(questions) - clustered_count
    )

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
