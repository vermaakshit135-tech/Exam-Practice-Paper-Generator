
import json
import time
import re
from pathlib import Path
from difflib import SequenceMatcher

from dotenv import load_dotenv
from google import genai
from google.genai import types


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

CLUSTERS_FILE = (
    BASE_DIR / "data" / "processed" / "question_clusters.json"
)

ANALYSIS_FILE = (
    BASE_DIR / "data" / "processed" / "topic_method_analysis.json"
)

OUTPUT_FILE = (
    BASE_DIR / "data" / "processed" / "cluster_validation_report.json"
)

MODEL = "gemini-3.8-flash"

MAX_RETRIES = 2


# --------------------------------------------------
# GEMINI INITIALIZATION
# --------------------------------------------------

load_dotenv(BASE_DIR / ".env")

client = genai.Client()


# --------------------------------------------------
# JSON HELPERS
# --------------------------------------------------

def load_json(file_path):
    if not file_path.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data, file_path):
    file_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )


# --------------------------------------------------
# TEXT NORMALIZATION
# --------------------------------------------------

def normalize_text(text):
    text = str(text or "").lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# --------------------------------------------------
# QUESTION METADATA
# --------------------------------------------------

def collect_question_metadata(data):
    """
    topic_method_analysis.json structure:

    {
        "analyses": [
            {
                "question": "...",
                "year": "...",
                "topic": "...",
                "subtopic": "...",
                "method": "...",
                "question_type": "..."
            }
        ]
    }

    The analysis file does not contain question IDs.
    We use the question text as the matching key.
    """

    metadata = {}

    analyses = data.get("analyses", [])

    if not isinstance(analyses, list):
        raise ValueError(
            "'analyses' must be a list in topic_method_analysis.json"
        )

    for item in analyses:
        if not isinstance(item, dict):
            continue

        question = str(
            item.get("question", "")
        ).strip()

        if not question:
            continue

        key = normalize_text(question)

        metadata[key] = {
            "question": question,
            "year": item.get("year"),
            "topic": item.get("topic"),
            "subtopic": item.get("subtopic"),
            "method": item.get("method"),
            "question_type": item.get("question_type"),
        }

    return metadata


# --------------------------------------------------
# CLUSTER HELPERS
# --------------------------------------------------

def get_clusters(data):
    """
    Supports common cluster JSON structures.
    """

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in (
            "clusters",
            "groups",
            "similar_groups"
        ):
            value = data.get(key)

            if isinstance(value, list):
                return value

    raise ValueError(
        "Could not find the clusters list in "
        "question_clusters.json. Check its JSON structure."
    )


def get_cluster_questions(cluster):
    if isinstance(cluster, list):
        return cluster

    if isinstance(cluster, dict):
        for key in (
            "questions",
            "members",
            "items"
        ):
            value = cluster.get(key)

            if isinstance(value, list):
                return value

    return []


def get_question_text(question):
    if isinstance(question, str):
        return question.strip()

    if isinstance(question, dict):
        for key in (
            "question",
            "question_text",
            "text"
        ):
            value = question.get(key)

            if value:
                return str(value).strip()

    return ""


def get_question_id(question, index):
    if isinstance(question, dict):
        for key in (
            "id",
            "question_id"
        ):
            value = question.get(key)

            if value is not None:
                return str(value)

    # Stable fallback within this cluster.
    return f"cluster_question_{index}"


# --------------------------------------------------
# MATCH QUESTIONS WITH METADATA
# --------------------------------------------------

def match_question_metadata(question_text, metadata):
    """
    First attempts exact normalized matching.
    If that fails, attempts fuzzy matching.

    Fuzzy matches below 0.85 are not automatically
    assigned metadata because a wrong match is risky.
    """

    normalized = normalize_text(question_text)

    if not normalized:
        return None

    if normalized in metadata:
        return metadata[normalized]

    best_match = None
    best_score = 0.0

    for stored_text, details in metadata.items():
        score = SequenceMatcher(
            None,
            normalized,
            stored_text
        ).ratio()

        if score > best_score:
            best_score = score
            best_match = details

    if best_match and best_score >= 0.85:
        return best_match

    return None


def enrich_cluster(cluster, metadata):
    enriched = []

    questions = get_cluster_questions(cluster)

    for index, question in enumerate(questions, start=1):
        question_text = get_question_text(question)

        question_id = get_question_id(
            question,
            index
        )

        matched_metadata = match_question_metadata(
            question_text,
            metadata
        )

        if matched_metadata:
            enriched.append({
                "id": question_id,
                "question": question_text
                or matched_metadata["question"],
                "year": matched_metadata.get("year"),
                "topic": matched_metadata.get("topic"),
                "subtopic": matched_metadata.get("subtopic"),
                "method": matched_metadata.get("method"),
                "question_type": matched_metadata.get(
                    "question_type"
                ),
                "metadata_matched": True,
            })

        else:
            enriched.append({
                "id": question_id,
                "question": question_text,
                "year": None,
                "topic": None,
                "subtopic": None,
                "method": None,
                "question_type": None,
                "metadata_matched": False,
            })

    return enriched


# --------------------------------------------------
# GEMINI CLUSTER VALIDATION
# --------------------------------------------------

def validate_cluster(cluster_id, questions):
    if len(questions) < 2:
        return {
            "cluster_id": cluster_id,
            "status": "review",
            "reason": "Fewer than two questions in this cluster.",
            "question_ids_to_keep": [],
            "question_ids_to_review_or_remove": [
                q["id"] for q in questions
            ],
            "validation_error": None,
        }

    question_data = [
        {
            "id": q["id"],
            "year": q.get("year"),
            "topic": q.get("topic"),
            "subtopic": q.get("subtopic"),
            "method": q.get("method"),
            "question_type": q.get("question_type"),
            "question": q["question"],
        }
        for q in questions
    ]

    prompt = f"""
You are validating groups of previous-year university exam questions.

Your goal is to determine whether the questions genuinely ask
the same or substantially equivalent question.

Rules:
1. Same broad topic does not automatically mean duplicate.
2. Different algorithms or different required tasks may be distinct.
3. Different input values for the same task may be similar variants.
4. OCR errors should be considered, but do not invent missing content.
5. Use "valid" when the questions genuinely ask substantially
   equivalent tasks.
6. Use "invalid" when the questions are clearly unrelated or
   substantially different in what they ask.
7. Use "review" when similarity is ambiguous or only partial.
8. Keep original question IDs exactly as supplied.
9. Every question ID must appear in exactly one of the two ID lists.
10. Do not claim validation succeeded if the question text is unclear.

Return only JSON in this format:
{{
  "status": "valid",
  "reason": "Short explanation",
  "question_ids_to_keep": ["id1"],
  "question_ids_to_review_or_remove": ["id2"]
}}

Cluster ID: {cluster_id}

Questions:
{json.dumps(question_data, ensure_ascii=False, indent=2)}
"""

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )

            if not response.text:
                raise ValueError(
                    "Gemini returned an empty response."
                )

            result = json.loads(response.text.strip())

            status = str(
                result.get("status", "review")
            ).lower()

            if status not in (
                "valid",
                "review",
                "invalid"
            ):
                status = "review"

            # Check that every supplied ID is accounted for.
            supplied_ids = {
                str(q["id"]) for q in questions
            }

            keep_ids = [
                str(value)
                for value in result.get(
                    "question_ids_to_keep", []
                )
            ]

            review_ids = [
                str(value)
                for value in result.get(
                    "question_ids_to_review_or_remove", []
                )
            ]

            returned_ids = set(keep_ids + review_ids)

            if (
                len(returned_ids) != len(keep_ids) + len(review_ids)
                or returned_ids != supplied_ids
            ):
                status = "review"

                reason = (
                    str(result.get("reason", ""))
                    + " ID lists were incomplete or inconsistent; "
                    "manual review is required."
                ).strip()

                keep_ids = []
                review_ids = sorted(supplied_ids)

            else:
                reason = str(
                    result.get(
                        "reason",
                        "No explanation provided."
                    )
                )

            return {
                "cluster_id": cluster_id,
                "status": status,
                "reason": reason,
                "question_ids_to_keep": keep_ids,
                "question_ids_to_review_or_remove": review_ids,
                "validation_error": None,
            }

        except Exception as error:
            error_text = str(error)
            print(
                f"Cluster {cluster_id}: "
                f"attempt {attempt + 1}/{MAX_RETRIES} failed."
            )
            print(error_text)

            # Quota exhaustion will not be fixed by retrying.
            if (
                "429" in error_text
                or "RESOURCE_EXHAUSTED" in error_text
                or "quota" in error_text.lower()
            ):
                return {
                    "cluster_id": cluster_id,
                    "status": "review",
                    "reason": (
                        "Gemini API quota exhausted. "
                        "This cluster was not validated."
                    ),
                    "question_ids_to_keep": [],
                    "question_ids_to_review_or_remove": [
                        q["id"] for q in questions
                    ],
                    "validation_error": error_text,
                }

            if attempt < MAX_RETRIES - 1:
                wait_seconds = 2 * (attempt + 1)

                print(
                    f"Retrying in {wait_seconds} seconds..."
                )

                time.sleep(wait_seconds)

            else:
                return {
                    "cluster_id": cluster_id,
                    "status": "review",
                    "reason": (
                        "Validation failed after retries. "
                        "Manual review is required."
                    ),
                    "question_ids_to_keep": [],
                    "question_ids_to_review_or_remove": [
                        q["id"] for q in questions
                    ],
                    "validation_error": error_text,
                }


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():
    print("Loading cluster and question data...")

    cluster_data = load_json(CLUSTERS_FILE)
    analysis_data = load_json(ANALYSIS_FILE)

    clusters = get_clusters(cluster_data)
    metadata = collect_question_metadata(analysis_data)

    print(f"Clusters found: {len(clusters)}")
    print(f"Question metadata records: {len(metadata)}")

    report = []

    for index, cluster in enumerate(clusters, start=1):
        if isinstance(cluster, dict):
            cluster_id = cluster.get(
                "cluster_id",
                cluster.get("id", index)
            )
        else:
            cluster_id = index

        questions = enrich_cluster(
            cluster,
            metadata
        )

        matched_count = sum(
            q["metadata_matched"]
            for q in questions
        )

        print(
            f"\nCluster {cluster_id}: "
            f"{len(questions)} questions, "
            f"{matched_count} metadata matches"
        )

        if not questions:
            result = {
                "cluster_id": cluster_id,
                "status": "review",
                "reason": (
                    "No questions could be extracted "
                    "from this cluster's structure."
                ),
                "question_ids_to_keep": [],
                "question_ids_to_review_or_remove": [],
                "validation_error": None,
            }

        elif any(not q["question"] for q in questions):
            result = {
                "cluster_id": cluster_id,
                "status": "review",
                "reason": (
                    "Some cluster entries have missing question text."
                ),
                "question_ids_to_keep": [],
                "question_ids_to_review_or_remove": [
                    q["id"] for q in questions
                ],
                "validation_error": None,
            }

        else:
            # Do not call Gemini when metadata matching is broken.
            # The original cluster questions can still be validated,
            # but matching must be inspected first.
            if matched_count == 0 and metadata:
                result = {
                    "cluster_id": cluster_id,
                    "status": "review",
                    "reason": (
                        "No question metadata matched. "
                        "Gemini was not called for this cluster."
                    ),
                    "question_ids_to_keep": [],
                    "question_ids_to_review_or_remove": [
                        q["id"] for q in questions
                    ],
                    "validation_error": None,
                }
            else:
                result = validate_cluster(
                    cluster_id,
                    questions
                )

        report.append(result)

        print(
            f"Status: {result['status'].upper()}"
        )
        print(
            f"Reason: {result['reason']}"
        )

        # Stop sending requests when quota exhaustion is detected.
        error_text = str(
            result.get("validation_error") or ""
        )

        if (
            "429" in error_text
            or "RESOURCE_EXHAUSTED" in error_text
            or "quota" in error_text.lower()
        ):
            print(
                "\nGemini quota exhausted. "
                "Remaining clusters will be marked as not validated."
            )

            current_index = index

            for remaining_index in range(
                current_index + 1,
                len(clusters) + 1
            ):
                remaining_cluster = clusters[
                    remaining_index - 1
                ]

                remaining_id = (
                    remaining_cluster.get(
                        "cluster_id",
                        remaining_cluster.get("id", remaining_index)
                    )
                    if isinstance(remaining_cluster, dict)
                    else remaining_index
                )

                remaining_questions = enrich_cluster(
                    remaining_cluster,
                    metadata
                )

                report.append({
                    "cluster_id": remaining_id,
                    "status": "review",
                    "reason": (
                        "Not validated because Gemini API quota "
                        "was exhausted during this run."
                    ),
                    "question_ids_to_keep": [],
                    "question_ids_to_review_or_remove": [
                        q["id"] for q in remaining_questions
                    ],
                    "validation_error": "API quota exhausted",
                })

            break

        time.sleep(1)

    save_json(report, OUTPUT_FILE)

    valid_count = sum(
        item["status"] == "valid"
        for item in report
    )

    review_count = sum(
        item["status"] == "review"
        for item in report
    )

    invalid_count = sum(
        item["status"] == "invalid"
        for item in report
    )

    not_validated_count = sum(
        bool(item.get("validation_error"))
        or "not validated" in item.get("reason", "").lower()
        or "quota exhausted" in item.get("reason", "").lower()
        for item in report
    )

    print("\n========== VALIDATION SUMMARY ==========")
    print(f"Valid clusters: {valid_count}")
    print(f"Review clusters: {review_count}")
    print(f"Invalid clusters: {invalid_count}")
    print(f"Not validated / API errors: {not_validated_count}")
    print(f"Report saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
