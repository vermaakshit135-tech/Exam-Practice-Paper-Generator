
import json
import os
import re
import time
from pathlib import Path
from xml.sax.saxutils import escape

from dotenv import load_dotenv
from google import genai
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
)

# --------------------------------------------------
# PATHS AND CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"
OUTPUT_DIR = BASE_DIR / "output"

PAPER_FILE = DATA_DIR / "generated_paper.json"
ANSWER_JSON = DATA_DIR / "answer_key.json"
ANSWER_PDF = OUTPUT_DIR / "answer_key.pdf"

load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

MAX_ATTEMPTS = 3
RETRY_DELAY = 3


# --------------------------------------------------
# GENERAL HELPERS
# --------------------------------------------------

def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_suffix(".tmp")

    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    temp_path.replace(path)


def get_question_text(item):
    """Extract question text from common JSON formats."""

    if isinstance(item, str):
        return item.strip()

    if isinstance(item, dict):
        for key in (
            "question",
            "question_text",
            "text",
            "content",
            "statement",
        ):
            value = item.get(key)

            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""


def get_marks(item, default=2):
    if isinstance(item, dict):
        value = item.get("marks", item.get("mark", default))

        try:
            return int(value)
        except (ValueError, TypeError):
            pass

    return default


def get_question_number(item, fallback):
    if isinstance(item, dict):
        for key in ("number", "question_number", "id", "q_no"):
            value = item.get(key)

            if value is not None:
                return str(value)

    return str(fallback)


def get_section_items(paper, *possible_keys):
    for key in possible_keys:
        value = paper.get(key)

        if isinstance(value, list):
            return value

    return []


def extract_options(item):
    """Support option_a/option_b and common options formats."""

    if not isinstance(item, dict):
        return []

    options = []

    # Format: {"option_a": "...", "option_b": "..."}
    for key, label in (
        ("option_a", "a"),
        ("option_b", "b"),
        ("option1", "a"),
        ("option2", "b"),
    ):
        value = item.get(key)

        if value is not None:
            text = get_question_text(value)

            if not text and isinstance(value, str):
                text = value.strip()

            if text:
                options.append((label, text))

    if options:
        return options

    # Format: {"options": {"a": "...", "b": "..."}}
    raw_options = item.get("options", item.get("alternatives"))

    if isinstance(raw_options, dict):
        for label, value in raw_options.items():
            text = get_question_text(value)

            if not text and isinstance(value, str):
                text = value.strip()

            if text:
                options.append((str(label).lower(), text))

    elif isinstance(raw_options, list):
        for index, value in enumerate(raw_options):
            text = get_question_text(value)

            if not text and isinstance(value, str):
                text = value.strip()

            if text:
                label = chr(97 + index)
                options.append((label, text))

    return options


# --------------------------------------------------
# ANSWER GENERATION WITH RETRY
# --------------------------------------------------

def generate_answer(client, question, marks, section):
    if not question.strip():
        raise ValueError("Question text is empty. Check generated_paper.json.")

    if marks <= 2:
        answer_style = (
            "Give a concise, accurate exam answer suitable for 2 marks. "
            "Use a definition or key points as appropriate."
        )
    else:
        answer_style = (
            "Give a well-structured university exam answer suitable for "
            f"{marks} marks. Include headings, explanations, algorithms, "
            "examples, equations, and complexity analysis where relevant."
        )

    prompt = f"""
You are an expert AKTU B.Tech examination answer writer.

Section: {section}
Marks: {marks}

Question:
{question}

Instructions:
1. Answer the exact question asked.
2. {answer_style}
3. Use clear, student-friendly academic English.
4. Use numbered steps or bullet points where helpful.
5. For algorithm questions, explain the algorithm and complexity.
6. For comparison questions, use a clear comparison.
7. Never invent missing graph, diagram, table, or input data.
8. If essential information is missing, explicitly state the limitation.
9. Return only the answer, without repeating the question.
"""

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
            )

            answer = (response.text or "").strip()

            if answer:
                return answer

            print(
                f"Empty response for {section}; "
                f"attempt {attempt}/{MAX_ATTEMPTS}"
            )

        except Exception as error:
            error_text = str(error)
            temporary_error = any(
                code in error_text
                for code in (
                    "503",
                    "429",
                    "500",
                    "502",
                    "504",
                    "UNAVAILABLE",
                    "RESOURCE_EXHAUSTED",
                    "INTERNAL",
                )
            )

            if not temporary_error or attempt == MAX_ATTEMPTS:
                raise

            print(
                f"Temporary API error for {section}; "
                f"attempt {attempt}/{MAX_ATTEMPTS}: {error_text[:200]}"
            )

        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_DELAY * attempt)

    raise RuntimeError(
        f"Could not generate an answer after {MAX_ATTEMPTS} attempts: "
        f"{section}"
    )


# --------------------------------------------------
# RESUMABLE ANSWER GENERATION
# --------------------------------------------------

def generate_all_answers(paper, client):
    # Checkpoint format: {"answers": {"SECTION_A_Q1": {...}}}
    if ANSWER_JSON.exists():
        try:
            saved = load_json(ANSWER_JSON)
        except (json.JSONDecodeError, OSError):
            saved = {}

        if isinstance(saved, dict) and isinstance(
            saved.get("answers"), dict
        ):
            answers = saved["answers"]
        else:
            answers = {}
    else:
        answers = {}

    tasks = []

    section_a = get_section_items(
        paper, "section_a", "SECTION_A", "section A"
    )
    section_b = get_section_items(
        paper, "section_b", "SECTION_B", "section B"
    )
    section_c = get_section_items(
        paper, "section_c", "SECTION_C", "section C"
    )

    # Sections A and B
    for section_name, items, default_marks in (
        ("SECTION_A", section_a, 2),
        ("SECTION_B", section_b, 7),
    ):
        for index, item in enumerate(items, start=1):
            question = get_question_text(item)

            if not question:
                print(
                    f"WARNING: Skipping {section_name} Q{index}; "
                    "question text was not found."
                )
                continue

            number = get_question_number(item, index)
            marks = get_marks(item, default_marks)
            answer_id = f"{section_name}_Q{number}"

            tasks.append({
                "id": answer_id,
                "section": section_name,
                "number": number,
                "label": f"Q{number}",
                "question": question,
                "marks": marks,
            })

    # Section C: generate answers for BOTH alternatives
    for index, item in enumerate(section_c, start=1):
        number = get_question_number(item, index)
        marks = get_marks(item, 7)
        options = extract_options(item)

        if options:
            for label, question in options:
                tasks.append({
                    "id": f"SECTION_C_Q{number}_{label}",
                    "section": "SECTION_C",
                    "number": number,
                    "label": f"Q{number} (Option {label})",
                    "question": question,
                    "marks": marks,
                })
        else:
            # Allow Section C items that contain one question only.
            question = get_question_text(item)

            if question:
                tasks.append({
                    "id": f"SECTION_C_Q{number}",
                    "section": "SECTION_C",
                    "number": number,
                    "label": f"Q{number}",
                    "question": question,
                    "marks": marks,
                })
            else:
                print(
                    f"WARNING: Section C Q{number} has no readable "
                    "question or alternatives. Check generated_paper.json."
                )

    if not tasks:
        raise ValueError(
            "No questions found. Check the structure of generated_paper.json."
        )

    print(f"Model: {MODEL}")
    print(f"Total answer tasks: {len(tasks)}")
    print(f"Already saved: {len(answers)}")

    for task in tasks:
        answer_id = task["id"]

        # Skip completed answers on a rerun.
        existing = answers.get(answer_id)

        if isinstance(existing, dict) and existing.get("answer", "").strip():
            print(f"Skipping saved answer: {task['label']}")
            continue

        print(f"Generating {task['section']} {task['label']}...")

        answer = generate_answer(
            client=client,
            question=task["question"],
            marks=task["marks"],
            section=task["section"],
        )

        answers[answer_id] = {
            "section": task["section"],
            "number": task["number"],
            "label": task["label"],
            "question": task["question"],
            "marks": task["marks"],
            "answer": answer,
        }

        # Save after every successful answer.
        save_json(ANSWER_JSON, {"answers": answers})
        print(f"Saved: {task['label']}")

        time.sleep(1)

    return answers


# --------------------------------------------------
# PDF GENERATION
# --------------------------------------------------

def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.drawCentredString(
        A4[0] / 2,
        0.4 * inch,
        f"Page {doc.page}",
    )
    canvas.restoreState()


def generate_pdf(answers):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="AnswerTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=18,
        leading=23,
        spaceAfter=18,
    ))

    styles.add(ParagraphStyle(
        name="QuestionHeading",
        parent=styles["Heading2"],
        fontSize=11,
        leading=15,
        spaceBefore=12,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="AnswerBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=15,
        spaceAfter=8,
    ))

    doc = SimpleDocTemplate(
        str(ANSWER_PDF),
        pagesize=A4,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.7 * inch,
    )

    story = [
        Paragraph("AKTU B.Tech Answer Key", styles["AnswerTitle"]),
        Paragraph(
            f"Generated using {escape(MODEL)}",
            styles["Normal"],
        ),
        Spacer(1, 16),
    ]

    section_titles = {
        "SECTION_A": "Section A — Short Answers",
        "SECTION_B": "Section B — Descriptive Answers",
        "SECTION_C": "Section C — Long Answers",
    }

    for section in ("SECTION_A", "SECTION_B", "SECTION_C"):
        section_answers = [
            item for item in answers.values()
            if item.get("section") == section
            and item.get("answer", "").strip()
        ]

        if not section_answers:
            continue

        if story:
            story.append(Spacer(1, 8))

        story.append(
            Paragraph(
                escape(section_titles[section]),
                styles["Heading1"],
            )
        )

        for item in section_answers:
            story.append(
                Paragraph(
                    escape(
                        f"{item.get('label', 'Question')} "
                        f"({item.get('marks', 0)} marks)"
                    ),
                    styles["QuestionHeading"],
                )
            )

            story.append(
                Paragraph(
                    escape(item.get("question", "")).replace("\n", "<br/>"),
                    styles["AnswerBody"],
                )
            )

            answer = escape(item["answer"]).replace("\n", "<br/>")

            story.append(
                Paragraph(answer, styles["AnswerBody"])
            )
            story.append(Spacer(1, 8))

    doc.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )

    print(f"\nAnswer key PDF saved: {ANSWER_PDF}")


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():
    if not API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is missing. Check the .env file."
        )

    if not PAPER_FILE.exists():
        raise FileNotFoundError(
            f"Generated paper not found: {PAPER_FILE}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    paper = load_json(PAPER_FILE)
    client = genai.Client(api_key=API_KEY)

    print("Generating answer key. Please wait...")
    print("Previously saved answers will be reused.")

    try:
        answers = generate_all_answers(paper, client)
    except Exception as error:
        print(f"\nGeneration stopped: {error}")
        print(f"Progress is saved in: {ANSWER_JSON}")
        print("Fix the issue and rerun this script to resume.")
        return

    save_json(ANSWER_JSON, {"answers": answers})
    generate_pdf(answers)

    print("\nAnswer key generated successfully.")
    print(f"JSON: {ANSWER_JSON}")
    print(f"PDF:  {ANSWER_PDF}")


if __name__ == "__main__":
    main()
