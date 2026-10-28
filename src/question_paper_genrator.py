
import json
import random
import re
from difflib import SequenceMatcher
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    KeepTogether,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"
OUTPUT_DIR = BASE_DIR / "output"

QUESTIONS_FILE = DATA_DIR / "questions.json"
PATTERN_FILE = DATA_DIR / "paper_pattern.json"
CLASSIFICATION_FILE = DATA_DIR / "question_classification.json"
LLM_ANALYSIS_FILE = DATA_DIR / "llm_analyzer.json"

OUTPUT_JSON = DATA_DIR / "generated_paper.json"
PAPER_PDF = OUTPUT_DIR / "question_paper.pdf"
ANSWER_KEY_PDF = OUTPUT_DIR / "answer_key.pdf"

RANDOM_SEED = 42
DUPLICATE_THRESHOLD = 0.84

TOPIC_KEYWORDS = {
    "recurrence": [
        "recurrence", "master method", "master theorem", "recursion tree"
    ],
    "red black tree": ["red black tree", "redblack tree"],
    "b tree": ["b-tree", "b tree"],
    "heaps": ["binomial heap", "fibonacci heap", "decrease key", "heap"],
    "minimum spanning tree": [
        "minimum spanning", "kruskal", "prim algorithm", "mst"
    ],
    "shortest path": [
        "shortest path", "dijkstra", "bellman ford", "floyd warshall"
    ],
    "dynamic programming": [
        "dynamic programming", "knapsack", "lcs",
        "travelling salesman", "traveling salesman", "tsp"
    ],
    "backtracking": [
        "backtracking", "branch and bound", "n queens", "subset sum"
    ],
    "string matching": ["kmp", "knuth morris pratt", "string matching"],
    "complexity": [
        "np complete", "np hard", "computational complexity", "time complexity"
    ],
    "approximation": [
        "approximation algorithm", "randomized algorithm",
        "set cover", "vertex cover"
    ],
    "sorting": [
        "heap sort", "merge sort", "counting sort",
        "insertion sort", "quick sort", "sorting algorithm"
    ],
    "convex hull": ["convex hull"],
    "divide and conquer": ["divide and conquer", "binary search", "merge sort"],
}


def load_json(path, required=True, default=None):
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Required file not found: {path}")
        return default if default is not None else {}

    with open(path, "r", encoding="utf-8-sig") as file:
        return json.load(file)


def clean_question(text):
    text = str(text or "").replace("\x0c", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \t\r\n-:;,.")


def normalize_question(text):
    text = clean_question(text).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def similarity_score(question_a, question_b):
    a = normalize_question(question_a)
    b = normalize_question(question_b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    sequence_score = SequenceMatcher(None, a, b).ratio()

    words_a = set(a.split())
    words_b = set(b.split())
    union = words_a | words_b

    jaccard_score = (
        len(words_a & words_b) / len(union)
        if union else 0.0
    )

    return max(sequence_score, jaccard_score)


def is_near_duplicate(question, existing_questions):
    return any(
        similarity_score(question, existing) >= DUPLICATE_THRESHOLD
        for existing in existing_questions
    )


def question_topic_matches(question):
    text = normalize_question(question)
    matches = []

    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(normalize_question(keyword) in text for keyword in keywords):
            matches.append(topic)

    return matches


def collect_questions(data):
    section_a = []
    section_b = []
    section_c = []

    if not isinstance(data, dict):
        raise ValueError("questions.json must contain a year-wise JSON object.")

    for year, year_data in data.items():
        if not isinstance(year_data, dict):
            continue

        for section in ("section_a", "section_b"):
            target = section_a if section == "section_a" else section_b

            for item in year_data.get(section, []):
                if isinstance(item, dict) and item.get("question"):
                    question = clean_question(item["question"])

                    if question:
                        target.append({
                            "year": str(item.get("year", year)),
                            "section": section,
                            "question": question,
                            "source_question": item,
                        })

        for item in year_data.get("section_c", []):
            if not isinstance(item, dict):
                continue

            alternatives = []

            for alt in item.get("alternatives", []):
                if isinstance(alt, dict) and alt.get("question"):
                    question = clean_question(alt["question"])

                    if question:
                        alternatives.append({
                            "question": question,
                            "year": str(alt.get("year", year)),
                            "source_question": alt,
                        })

            if len(alternatives) >= 2:
                section_c.append({
                    "year": str(item.get("year", year)),
                    "question_number": item.get("question_number"),
                    "alternatives": alternatives,
                })

    return section_a, section_b, section_c


def deduplicate(items):
    unique = []
    seen = set()

    for item in items:
        key = normalize_question(item["question"])

        if key and key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


def load_classification():
    data = load_json(
        CLASSIFICATION_FILE,
        required=False,
        default={}
    )

    result = {}

    if isinstance(data, dict):
        for item in data.get("questions", []):
            if isinstance(item, dict) and item.get("question"):
                result[normalize_question(item["question"])] = item

    return result


def load_important_topics(analysis):
    topics = (
        analysis.get("important_topics", [])
        if isinstance(analysis, dict)
        else []
    )

    return [
        str(item.get("topic", item.get("name", "")))
        if isinstance(item, dict)
        else str(item)
        for item in topics
    ]


def get_question_score(question, important_topics, classification_map):
    text = normalize_question(question)
    score = 0
    topics = question_topic_matches(question)

    for important in important_topics:
        normalized_important = normalize_question(important)

        if normalized_important and (
            normalized_important in text
            or any(
                normalized_important in normalize_question(topic)
                or normalize_question(topic) in normalized_important
                for topic in topics
            )
        ):
            score += 3

    classification = classification_map.get(text, {})

    if classification.get("classification") == "SIMILAR":
        score += 1

    if len(text) >= 20:
        score += 1

    if len(text) > 450:
        score -= 1

    return score


def select_candidates(
    candidates,
    count,
    get_texts,
    important_topics,
    classification_map,
    selected_texts,
    rng,
    section_name,
):
    candidates = list(candidates)
    rng.shuffle(candidates)

    ranked = sorted(
        candidates,
        key=lambda item: sum(
            get_question_score(
                question,
                important_topics,
                classification_map,
            )
            for question in get_texts(item)
        ),
        reverse=True,
    )

    chosen = []
    chosen_topics = set()

    # First prefer topic diversity, then allow topic repeats if needed.
    for allow_topic_repeat in (False, True):
        for item in ranked:
            if item in chosen:
                continue

            texts = get_texts(item)

            if any(
                is_near_duplicate(question, selected_texts)
                for question in texts
            ):
                continue

            duplicate_alternatives = any(
                is_near_duplicate(texts[i], [texts[j]])
                for i in range(len(texts))
                for j in range(i + 1, len(texts))
            )

            if duplicate_alternatives:
                continue

            topics = set()

            for question in texts:
                topics.update(question_topic_matches(question))

            if not allow_topic_repeat and topics & chosen_topics:
                continue

            chosen.append(item)
            selected_texts.extend(texts)
            chosen_topics.update(topics)

            if len(chosen) == count:
                return chosen

    if len(chosen) < count:
        raise ValueError(
            f"Only {len(chosen)} of {count} required questions could be "
            f"selected for {section_name}. Review available PYQs or "
            "DUPLICATE_THRESHOLD."
        )

    return chosen


def select_paper(data, pattern, analysis, classification_map):
    section_a, section_b, section_c = collect_questions(data)

    section_a = deduplicate(section_a)
    section_b = deduplicate(section_b)

    important_topics = load_important_topics(analysis)

    required_a = int(pattern["section_a"]["attempt"])
    required_b = int(pattern["section_b"]["questions"])
    required_c = int(pattern["section_c"]["questions"])

    selected_texts = []
    rng = random.Random(RANDOM_SEED)

    selected_a = select_candidates(
        section_a,
        required_a,
        lambda item: [item["question"]],
        important_topics,
        classification_map,
        selected_texts,
        rng,
        "Section A",
    )

    selected_b = select_candidates(
        section_b,
        required_b,
        lambda item: [item["question"]],
        important_topics,
        classification_map,
        selected_texts,
        rng,
        "Section B",
    )

    selected_c = select_candidates(
        section_c,
        required_c,
        lambda item: [
            alt["question"]
            for alt in item["alternatives"][:2]
        ],
        important_topics,
        classification_map,
        selected_texts,
        rng,
        "Section C",
    )

    for number, item in enumerate(selected_c, start=1):
        item["paper_question_number"] = number

    return {
        "time": pattern.get("time", "3 Hours"),
        "max_marks": pattern.get("max_marks", 70),
        "subject": "Design and Analysis of Algorithms",
        "section_a": selected_a,
        "section_b": selected_b,
        "section_c": selected_c,
    }


def save_paper_json(paper):
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as file:
        json.dump(paper, file, indent=4, ensure_ascii=False)


def safe_paragraph(text, style):
    return Paragraph(escape(str(text)), style)


def create_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="PaperTitleCustom",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=15,
        leading=19,
        spaceAfter=8,
    ))

    styles.add(ParagraphStyle(
        name="SectionHeadingCustom",
        parent=styles["Heading2"],
        fontSize=12,
        leading=15,
        spaceBefore=12,
        spaceAfter=7,
        textColor=colors.darkblue,
    ))

    styles.add(ParagraphStyle(
        name="QuestionTextCustom",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        spaceAfter=7,
    ))

    return styles


def generate_question_paper_pdf(paper, pattern):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(PAPER_PDF),
        pagesize=A4,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )

    styles = create_styles()

    a_pattern = pattern["section_a"]
    b_pattern = pattern["section_b"]
    c_pattern = pattern["section_c"]

    story = [
        Paragraph(
            "AKTU B.Tech Examination",
            styles["PaperTitleCustom"],
        ),
        Paragraph(
            f"Subject: {escape(paper['subject'])}",
            styles["PaperTitleCustom"],
        ),
        Spacer(1, 8),
        safe_paragraph(
            f"Time: {paper['time']}     "
            f"Maximum Marks: {paper['max_marks']}",
            styles["BodyText"],
        ),
        Spacer(1, 10),
        Paragraph("Instructions", styles["Heading3"]),
        safe_paragraph(
            f"1. Section A: Attempt all {a_pattern['attempt']} questions. "
            f"Each carries {a_pattern['marks_each']} marks.",
            styles["BodyText"],
        ),
        safe_paragraph(
            f"2. Section B: Attempt any {b_pattern['attempt']} out of "
            f"{b_pattern['questions']} questions. Each carries "
            f"{b_pattern['marks_each']} marks.",
            styles["BodyText"],
        ),
        safe_paragraph(
            f"3. Section C: Attempt {c_pattern['attempt']} questions. "
            "Each has two alternatives; attempt one alternative per "
            f"question. Each carries {c_pattern['marks_each']} marks.",
            styles["BodyText"],
        ),
    ]

    story.append(Paragraph(
        f"SECTION A — {a_pattern['marks_each']} Marks Each",
        styles["SectionHeadingCustom"],
    ))

    for number, item in enumerate(paper["section_a"], start=1):
        story.append(safe_paragraph(
            f"{number}. {item['question']}",
            styles["QuestionTextCustom"],
        ))

    story.append(Paragraph(
        f"SECTION B — {b_pattern['marks_each']} Marks Each",
        styles["SectionHeadingCustom"],
    ))

    for number, item in enumerate(paper["section_b"], start=1):
        story.append(safe_paragraph(
            f"{number}. {item['question']}",
            styles["QuestionTextCustom"],
        ))

    story.append(Paragraph(
        f"SECTION C — {c_pattern['marks_each']} Marks Each",
        styles["SectionHeadingCustom"],
    ))

    for item in paper["section_c"]:
        alternatives = item["alternatives"]
        number = item["paper_question_number"]

        question_block = [
            safe_paragraph(
                f"Q{number}. Attempt either option:",
                styles["QuestionTextCustom"],
            ),
            safe_paragraph(
                f"(a) {alternatives[0]['question']}",
                styles["QuestionTextCustom"],
            ),
            safe_paragraph(
                f"(b) {alternatives[1]['question']}",
                styles["QuestionTextCustom"],
            ),
            Spacer(1, 5),
        ]

        story.append(KeepTogether(question_block))

    doc.build(story)


def collect_answers(analysis):
    lookup = {}

    if not isinstance(analysis, dict):
        return lookup

    for field in ("answers", "question_answers", "solutions"):
        values = analysis.get(field, [])

        if isinstance(values, dict):
            for question, answer in values.items():
                lookup[normalize_question(question)] = answer

        elif isinstance(values, list):
            for item in values:
                if not isinstance(item, dict):
                    continue

                question = item.get("question", "")
                answer = item.get("answer", item.get("solution", ""))

                if question and answer:
                    lookup[normalize_question(question)] = answer

    return lookup


def get_answer_for_question(question_item, answer_lookup):
    question = question_item.get("question", "")
    answer = answer_lookup.get(normalize_question(question))

    if isinstance(answer, dict):
        answer = answer.get("answer", answer.get("solution", ""))

    if isinstance(answer, str) and answer.strip():
        return answer.strip()

    return (
        "Answer/solution is not available in the loaded source data. "
        "Verify and add a correct solution before using this as an answer key."
    )


def generate_answer_key_pdf(paper, analysis):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(ANSWER_KEY_PDF),
        pagesize=A4,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )

    styles = create_styles()
    answer_lookup = collect_answers(analysis)

    story = [
        Paragraph(
            "AKTU B.Tech Examination — Answer Key",
            styles["PaperTitleCustom"],
        ),
        Paragraph(
            f"Subject: {escape(paper['subject'])}",
            styles["PaperTitleCustom"],
        ),
        Spacer(1, 10),
        safe_paragraph(
            "Answers are included only when available in the source analysis. "
            "Missing solutions are flagged for verification.",
            styles["BodyText"],
        ),
    ]

    for section_name, label in (
        ("section_a", "SECTION A"),
        ("section_b", "SECTION B"),
    ):
        story.append(Paragraph(label, styles["SectionHeadingCustom"]))

        for number, item in enumerate(paper[section_name], start=1):
            answer = get_answer_for_question(item, answer_lookup)

            story.append(KeepTogether([
                safe_paragraph(
                    f"{number}. {item['question']}",
                    styles["QuestionTextCustom"],
                ),
                safe_paragraph(
                    f"Answer: {answer}",
                    styles["QuestionTextCustom"],
                ),
            ]))

    story.append(Paragraph(
        "SECTION C",
        styles["SectionHeadingCustom"],
    ))

    for item in paper["section_c"]:
        number = item["paper_question_number"]
        story.append(safe_paragraph(
            f"Q{number}",
            styles["Heading3"],
        ))

        for option_label, alt in zip(("a", "b"), item["alternatives"][:2]):
            answer = get_answer_for_question(alt, answer_lookup)

            story.append(KeepTogether([
                safe_paragraph(
                    f"({option_label}) {alt['question']}",
                    styles["QuestionTextCustom"],
                ),
                safe_paragraph(
                    f"Answer: {answer}",
                    styles["QuestionTextCustom"],
                ),
            ]))

    doc.build(story)


def main():
    questions_data = load_json(QUESTIONS_FILE)
    pattern = load_json(PATTERN_FILE)
    analysis = load_json(
        LLM_ANALYSIS_FILE,
        required=False,
        default={},
    )
    classification_map = load_classification()

    paper = select_paper(
        questions_data,
        pattern,
        analysis,
        classification_map,
    )

    save_paper_json(paper)
    generate_question_paper_pdf(paper, pattern)
    generate_answer_key_pdf(paper, analysis)

    print("\nQUESTION PAPER GENERATION COMPLETED")
    print(f"Section A: {len(paper['section_a'])} questions")
    print(f"Section B: {len(paper['section_b'])} questions")
    print(f"Section C: {len(paper['section_c'])} questions")
    print(f"Maximum marks: {paper['max_marks']}")
    print(f"JSON saved: {OUTPUT_JSON}")
    print(f"Question paper PDF: {PAPER_PDF}")
    print(f"Answer key PDF: {ANSWER_KEY_PDF}")
    print(
        "Note: Answer-key entries without source solutions "
        "require verification."
    )


if __name__ == "__main__":
    main()
