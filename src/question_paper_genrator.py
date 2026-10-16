
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

PROCESSED_DIR = BASE_DIR / "data" / "processed"

PATTERN_FILE = PROCESSED_DIR / "paper_pattern.json"
QUESTIONS_FILE = PROCESSED_DIR / "questions.json"
CLUSTERS_FILE = PROCESSED_DIR / "question_clusters.json"
OUTPUT_FILE = PROCESSED_DIR / "generated_paper.json"


def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def main():
    # Load input files
    questions_data = load_json(QUESTIONS_FILE)
    clusters_data = load_json(CLUSTERS_FILE)
    pattern_data = load_json(PATTERN_FILE)

    # Display exam pattern
    print("\nPaper Pattern Loaded:")
    print("Time:", pattern_data["time"])
    print("Maximum Marks:", pattern_data["max_marks"])
    print("Section A:", pattern_data["section_a"])
    print("Section B:", pattern_data["section_b"])
    print("Section C:", pattern_data["section_c"])

    # Display first cluster for inspection
    print("\nFirst cluster sample:")
    if clusters_data:
        print(json.dumps(
            clusters_data[0],
            indent=4,
            ensure_ascii=False
        ))
    else:
        print("No clusters found.")

    all_questions = []

    # Collect questions from all years
    for year, year_data in questions_data.items():
        for section, questions in year_data.items():
            for item in questions:

                # Section C: collect every alternative
                if isinstance(item, dict) and "alternatives" in item:
                    for alternative in item["alternatives"]:
                        if (
                            isinstance(alternative, dict)
                            and "question" in alternative
                        ):
                            all_questions.append({
                                "year": year,
                                "section": section,
                                "question": alternative["question"],
                                "marker": alternative.get("marker"),
                                "question_number": item.get(
                                    "question_number"
                                )
                            })

                # Section A and B: collect normal questions
                elif isinstance(item, dict) and "question" in item:
                    all_questions.append({
                        "year": year,
                        "section": section,
                        "question": item["question"],
                        "marker": item.get("marker")
                    })

    # Display loading summary
    print("\nQuestions data loaded successfully!")
    print("Clusters data loaded successfully!")
    print("Years found:", len(questions_data))
    print("Clusters count:", len(clusters_data))
    print("Total questions collected:", len(all_questions))

    # Count questions across all years by section
    print("\nAvailable questions by section:")

    for section in ["section_a", "section_b", "section_c"]:
        count = sum(
            1
            for question in all_questions
            if question["section"] == section
        )
        print(f"{section}: {count}")

    # Display first collected question
    if all_questions:
        print("\nFirst collected question:")
        print(all_questions[0])

    # Count questions by year and section
    print("\nQuestions collected by year and section:")

    for year in questions_data:
        print("\n", year)

        for section in ["section_a", "section_b", "section_c"]:
            count = sum(
                1
                for question in all_questions
                if question["year"] == year
                and question["section"] == section
            )
            print(section, ":", count)

    # Save collected questions
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            all_questions,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("\nCollected questions saved to:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
