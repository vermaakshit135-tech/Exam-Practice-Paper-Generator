
import json
from pathlib import Path
from collections import defaultdict


# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data" / "processed"

INPUT_FILE = DATA_DIR / "topic_method_analysis.json"
OUTPUT_FILE = DATA_DIR / "topic_method_frequency.json"


def load_analysis():
    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    return data["analyses"]


def calculate_frequency(analyses):
    topic_data = defaultdict(
        lambda: {"question_count": 0, "years": set()}
    )

    method_data = defaultdict(
        lambda: {"question_count": 0, "years": set()}
    )

    for item in analyses:
        topic = item.get("topic", "Unknown")
        method = item.get("method", "Not specified")
        year = item.get("year", "Unknown")

        # Count topics
        topic_data[topic]["question_count"] += 1
        topic_data[topic]["years"].add(year)

        # Count methods, excluding unspecified methods
        if method and method != "Not specified":
            method_data[method]["question_count"] += 1
            method_data[method]["years"].add(year)

    topic_frequency = []

    for topic, details in topic_data.items():
        topic_frequency.append({
            "topic": topic,
            "question_count": details["question_count"],
            "year_count": len(details["years"]),
            "years": sorted(details["years"])
        })

    method_frequency = []

    for method, details in method_data.items():
        method_frequency.append({
            "method": method,
            "question_count": details["question_count"],
            "year_count": len(details["years"]),
            "years": sorted(details["years"])
        })

    topic_frequency.sort(
        key=lambda item: item["question_count"],
        reverse=True
    )

    method_frequency.sort(
        key=lambda item: item["question_count"],
        reverse=True
    )

    return {
        "total_questions_analyzed": len(analyses),
        "topic_frequency": topic_frequency,
        "method_frequency": method_frequency
    }


def save_results(results):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            results,
            file,
            ensure_ascii=False,
            indent=4
        )

    print("\nFrequency report saved to:", OUTPUT_FILE)


def main():
    analyses = load_analysis()

    results = calculate_frequency(analyses)

    save_results(results)

    print("\nTOPIC FREQUENCY")
    print("-" * 40)

    for item in results["topic_frequency"][:10]:
        print(
            f'{item["topic"]}: '
            f'{item["question_count"]} questions, '
            f'{item["year_count"]} years'
        )

    print("\nMETHOD FREQUENCY")
    print("-" * 40)

    for item in results["method_frequency"][:10]:
        print(
            f'{item["method"]}: '
            f'{item["question_count"]} questions, '
            f'{item["year_count"]} years'
        )


if __name__ == "__main__":
    main()
