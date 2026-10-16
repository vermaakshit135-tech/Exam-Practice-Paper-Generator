import json
import re
from pathlib import Path
from collections import Counter, defaultdict


# ============================================================
# FILE PATHS
# ============================================================

INPUT_FILE = Path("data/processed/questions.json")
OUTPUT_FILE = Path("data/processed/analysis.json")


# ============================================================
# LOAD QUESTIONS
# ============================================================

def load_questions():
    """Load extracted questions from questions.json."""

    if not INPUT_FILE.exists():
        print(f"ERROR: File not found: {INPUT_FILE}")
        return None

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        print("questions.json loaded successfully.")
        return data

    except json.JSONDecodeError as error:
        print(f"ERROR: Invalid JSON: {error}")
        return None


# ============================================================
# NORMALIZE QUESTION
# ============================================================

def normalize_question(text):
    """
    Normalize question text so that exact/similar textual
    comparisons become easier.
    """

    if not text:
        return ""

    text = text.lower()

    # Remove page separators
    text = re.sub(
        r"===== page \d+ =====",
        " ",
        text,
        flags=re.IGNORECASE
    )

    # Remove excessive spaces
    text = " ".join(text.split())

    # Remove common marks at the end
    text = re.sub(
        r"\s+\d+\s*$",
        "",
        text
    )

    return text.strip()


# ============================================================
# ADD QUESTION
# ============================================================

def add_question(
    question_records,
    paper_name,
    section,
    question_text,
    question_number=None,
    marker=None
):
    """Store one extracted question in a common format."""

    if not question_text:
        return

    question_text = question_text.strip()

    normalized = normalize_question(question_text)

    if not normalized:
        return

    question_records.append({
        "paper": paper_name,
        "section": section,
        "question_number": question_number,
        "marker": marker,
        "question": question_text,
        "normalized_question": normalized
    })


# ============================================================
# EXTRACT ALL QUESTIONS
# ============================================================

def extract_all_questions(data):
    """
    Convert the current questions.json structure into
    one flat list of individual questions.
    """

    records = []

    for paper_name, paper_data in data.items():

        # ----------------------------------------------------
        # SECTION A
        # ----------------------------------------------------

        for item in paper_data.get("section_a", []):

            add_question(
                question_records=records,
                paper_name=paper_name,
                section="A",
                question_text=item.get("question", ""),
                marker=item.get("marker")
            )

        # ----------------------------------------------------
        # SECTION B
        # ----------------------------------------------------

        for item in paper_data.get("section_b", []):

            add_question(
                question_records=records,
                paper_name=paper_name,
                section="B",
                question_text=item.get("question", ""),
                marker=item.get("marker")
            )

        # ----------------------------------------------------
        # SECTION C
        # ----------------------------------------------------

        for main_question in paper_data.get("section_c", []):

            question_number = main_question.get(
                "question_number"
            )

            alternatives = main_question.get(
                "alternatives",
                []
            )

            for alternative in alternatives:

                add_question(
                    question_records=records,
                    paper_name=paper_name,
                    section="C",
                    question_text=alternative.get(
                        "question",
                        ""
                    ),
                    question_number=question_number,
                    marker=alternative.get("marker")
                )

    return records


# ============================================================
# BASIC STATISTICS
# ============================================================

def calculate_statistics(records, data):
    """Calculate basic dataset statistics."""

    section_counts = Counter()

    paper_counts = Counter()

    question_frequency = Counter()

    question_years = defaultdict(set)

    question_details = defaultdict(list)

    # --------------------------------------------------------
    # Process every question
    # --------------------------------------------------------

    for record in records:

        paper = record["paper"]
        section = record["section"]
        normalized = record["normalized_question"]

        section_counts[section] += 1
        paper_counts[paper] += 1

        question_frequency[normalized] += 1

        question_years[normalized].add(paper)

        question_details[normalized].append({
            "paper": paper,
            "section": section,
            "question_number": record["question_number"],
            "marker": record["marker"],
            "question": record["question"]
        })

    # --------------------------------------------------------
    # Convert sets to lists
    # --------------------------------------------------------

    question_years = {
        question: sorted(list(years))
        for question, years in question_years.items()
    }

    # --------------------------------------------------------
    # Repeated questions
    # --------------------------------------------------------

    repeated_questions = []

    for question, frequency in question_frequency.items():

        if frequency > 1:

            repeated_questions.append({
                "question": question,
                "frequency": frequency,
                "years": question_years[question],
                "details": question_details[question]
            })

    repeated_questions.sort(
        key=lambda item: item["frequency"],
        reverse=True
    )

    # --------------------------------------------------------
    # Year-wise statistics
    # --------------------------------------------------------

    year_wise = {}

    for paper_name, paper_data in data.items():

        section_a_count = len(
            paper_data.get("section_a", [])
        )

        section_b_count = len(
            paper_data.get("section_b", [])
        )

        section_c_main = len(
            paper_data.get("section_c", [])
        )

        section_c_alternatives = sum(
            len(
                question.get(
                    "alternatives",
                    []
                )
            )
            for question in paper_data.get(
                "section_c",
                []
            )
        )

        year_wise[paper_name] = {
            "section_a": section_a_count,
            "section_b": section_b_count,
            "section_c_main_questions": section_c_main,
            "section_c_alternatives": section_c_alternatives,
            "total_individual_questions": (
                section_a_count
                + section_b_count
                + section_c_alternatives
            )
        }

    # --------------------------------------------------------
    # Final statistics
    # --------------------------------------------------------

    statistics = {
        "total_individual_questions": len(records),

        "unique_exact_questions": len(
            question_frequency
        ),

        "section_wise_count": dict(
            section_counts
        ),

        "paper_wise_count": dict(
            paper_counts
        ),

        "year_wise": year_wise,

        "question_frequency": dict(
            question_frequency
        ),

        "question_years": question_years,

        "repeated_questions": repeated_questions
    }

    return statistics


# ============================================================
# FIND QUESTIONS APPEARING IN MULTIPLE YEARS
# ============================================================

def find_multi_year_questions(records):
    """
    Find questions that appeared in more than one paper/year.
    """

    question_data = defaultdict(
        lambda: {
            "years": set(),
            "occurrences": []
        }
    )

    for record in records:

        normalized = record["normalized_question"]

        question_data[normalized]["years"].add(
            record["paper"]
        )

        question_data[normalized]["occurrences"].append({
            "paper": record["paper"],
            "section": record["section"],
            "question": record["question"]
        })

    multi_year = []

    for question, info in question_data.items():

        if len(info["years"]) > 1:

            multi_year.append({
                "question": question,
                "years": sorted(
                    list(info["years"])
                ),
                "year_count": len(
                    info["years"]
                ),
                "occurrences": info["occurrences"]
            })

    multi_year.sort(
        key=lambda item: item["year_count"],
        reverse=True
    )

    return multi_year


# ============================================================
# FIND SECTION-WISE QUESTIONS
# ============================================================

def section_questions(records):

    result = {
        "A": [],
        "B": [],
        "C": []
    }

    for record in records:

        result[record["section"]].append({
            "paper": record["paper"],
            "question_number": record["question_number"],
            "marker": record["marker"],
            "question": record["question"]
        })

    return result


# ============================================================
# BUILD FINAL ANALYSIS
# ============================================================

def analyze_questions(data):

    records = extract_all_questions(data)

    statistics = calculate_statistics(
        records,
        data
    )

    multi_year_questions = find_multi_year_questions(
        records
    )

    section_data = section_questions(
        records
    )

    analysis = {
        "dataset": {
            "papers": list(data.keys()),
            "number_of_papers": len(data)
        },

        "statistics": statistics,

        "multi_year_questions": multi_year_questions,

        "section_questions": section_data,

        "all_questions": records
    }

    return analysis


# ============================================================
# SAVE ANALYSIS
# ============================================================

def save_analysis(analysis):

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            analysis,
            file,
            indent=4,
            ensure_ascii=False
        )

    print()
    print(
        f"Saved analysis to: {OUTPUT_FILE}"
    )


# ============================================================
# SHOW SUMMARY
# ============================================================

def show_summary(analysis):

    stats = analysis["statistics"]

    print()
    print("=" * 70)
    print("QUESTION ANALYSIS SUMMARY")
    print("=" * 70)

    print(
        f"Total individual questions: "
        f"{stats['total_individual_questions']}"
    )

    print(
        f"Unique exact questions: "
        f"{stats['unique_exact_questions']}"
    )

    print()

    # --------------------------------------------------------
    # Section counts
    # --------------------------------------------------------

    print("SECTION-WISE COUNT")
    print("-" * 40)

    for section, count in stats[
        "section_wise_count"
    ].items():

        print(
            f"Section {section}: {count}"
        )

    # --------------------------------------------------------
    # Year-wise counts
    # --------------------------------------------------------

    print()
    print("YEAR-WISE ANALYSIS")
    print("-" * 70)

    for paper, info in stats[
        "year_wise"
    ].items():

        print(
            f"{paper}: "
            f"A={info['section_a']}, "
            f"B={info['section_b']}, "
            f"C-main={info['section_c_main_questions']}, "
            f"C-alternatives={info['section_c_alternatives']}, "
            f"Total={info['total_individual_questions']}"
        )

    # --------------------------------------------------------
    # Repeated questions
    # --------------------------------------------------------

    repeated = stats[
        "repeated_questions"
    ]

    print()
    print(
        f"Exact repeated questions: "
        f"{len(repeated)}"
    )

    print()
    print("TOP REPEATED QUESTIONS")
    print("-" * 70)

    if not repeated:

        print(
            "No exact repeated questions found."
        )

    else:

        for index, item in enumerate(
            repeated[:10],
            start=1
        ):

            print()
            print(
                f"{index}. "
                f"Frequency: {item['frequency']}"
            )

            print(
                "Years: "
                + ", ".join(item["years"])
            )

            print(
                "Question: "
                + item["question"]
            )

    # --------------------------------------------------------
    # Multi-year questions
    # --------------------------------------------------------

    multi_year = analysis[
        "multi_year_questions"
    ]

    print()
    print(
        f"Questions appearing in multiple papers: "
        f"{len(multi_year)}"
    )

    print()
    print("TOP MULTI-YEAR QUESTIONS")
    print("-" * 70)

    for index, item in enumerate(
        multi_year[:10],
        start=1
    ):

        print()

        print(
            f"{index}. Appeared in "
            f"{item['year_count']} papers"
        )

        print(
            "Years: "
            + ", ".join(item["years"])
        )

        print(
            "Question: "
            + item["question"]
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("QUESTION ANALYZER")
    print("=" * 70)

    data = load_questions()

    if data is None:
        return

    print(
        f"Found {len(data)} papers."
    )

    analysis = analyze_questions(
        data
    )

    save_analysis(
        analysis
    )

    show_summary(
        analysis
    )

    print()
    print("=" * 70)
    print("QUESTION ANALYSIS COMPLETED")
    print("=" * 70)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()