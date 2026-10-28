
import json
import re
from pathlib import Path


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text):
    """Fix common encoding issues and remove PDF footer noise."""

    replacements = {
        "â€™": "'",
        "â€˜": "'",
        "â€œ": '"',
        "â€": '"',
        "â€“": "-",
        "â€”": "-",
        "â€¦": "...",
        "Ã—": "x",
        "Â°": " degrees ",
        "Â": "",
        "\ufffd": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove page separator labels.
    text = re.sub(
        r"(?m)^\s*===== PAGE \d+ =====\s*$",
        "",
        text
    )

    # Remove footer text, even if merged into a question.
    text = re.sub(
        r"\s*MANISH KUMAR JHA\s*\|.*?"
        r"(?=Sub\s*Code\b|$)",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    # Remove remaining printed-page footer text.
    text = re.sub(
        r"\s*Printed Page\s+\d+\s+of\s+\d+.*$",
        "",
        text,
        flags=re.IGNORECASE
    )

    # Clean accidental repeated spaces.
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


# ============================================================
# GENERIC QUESTION MARKER
# ============================================================

def get_marker(line):
    line = line.strip()

    match = re.match(r"^\(([a-zA-Z])\)\s*", line)
    if match:
        return match.group(1).lower()

    match = re.match(r"^([a-zA-Z])[.):]\s*", line)
    if match:
        return match.group(1).lower()

    # Common OCR mistakes.
    if re.match(r"^\(6\)\s*", line):
        return "b"

    if re.match(r"^\(>\)\s*", line):
        return "b"

    return None


def remove_marker(line):
    line = re.sub(r"^\([a-zA-Z]\)\s*", "", line)
    line = re.sub(r"^\([6>]\)\s*", "", line)
    line = re.sub(r"^[a-zA-Z][.):]\s*", "", line)
    return line.strip()


# ============================================================
# GENERIC MARKED QUESTION EXTRACTION
# ============================================================

def extract_marked_questions(text):
    lines = text.splitlines()

    questions = []
    current_marker = None
    current_text = []

    for line in lines:
        line = line.strip()

        if not line:
            continue

        marker = get_marker(line)

        if marker:
            if current_marker is not None:
                question = normalize_text(" ".join(current_text))
                if question:
                    questions.append({
                        "marker": current_marker,
                        "question": question
                    })

            current_marker = marker
            current_text = [remove_marker(line)]

        elif current_marker is not None:
            current_text.append(line)

    if current_marker is not None:
        question = normalize_text(" ".join(current_text))
        if question:
            questions.append({
                "marker": current_marker,
                "question": question
            })

    return questions


# ============================================================
# SECTION A
# ============================================================

def extract_section_a(text, filename):

    if filename.startswith("o18-19"):
        start = text.find("SECTION A")
        end = text.find("Attempt any three of the following")

        if start == -1 or end == -1:
            return []

        section_text = text[start:end]

        section_text = re.sub(
            r"(?m)^a\s+[-—_]+\s*",
            "a. ",
            section_text
        )

        section_text = re.sub(
            r"(?m)^[¢©]\s*[.)]?\s*",
            "e. ",
            section_text
        )

        section_text = re.sub(
            r"(?m)^f[,\s]+",
            "f. ",
            section_text
        )

        questions = extract_marked_questions(section_text)
        fixed = []

        for q in questions:
            if q["marker"] == "e":
                question = q["question"]

                split = re.split(
                    r"\ba\s+PY\s+f\s*,?\s*",
                    question,
                    maxsplit=1,
                    flags=re.IGNORECASE
                )

                if len(split) == 2:
                    fixed.append({
                        "marker": "e",
                        "question": split[0].strip()
                    })
                    fixed.append({
                        "marker": "f",
                        "question": split[1].strip()
                    })
                else:
                    split = re.split(
                        r"\bf\s*,\s*(What are)",
                        question,
                        maxsplit=1,
                        flags=re.IGNORECASE
                    )

                    if len(split) == 3:
                        fixed.append({
                            "marker": "e",
                            "question": split[0].strip()
                        })
                        fixed.append({
                            "marker": "f",
                            "question": (
                                split[1] + split[2]
                            ).strip()
                        })
                    else:
                        fixed.append(q)
            else:
                fixed.append(q)

        return [
            q for q in fixed
            if q["marker"] in "abcdefg"
        ][:7]

    match = re.search(
        r"SECTION[- ]?A(.*?)(?=SECTION[- ]?B|SECTION[- ]?C|$)",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if match:
        return extract_marked_questions(match.group(1))

    return []


# ============================================================
# SECTION B
# ============================================================

def extract_section_b(text, filename):

    if filename.startswith("o18-19"):
        start = text.find("Attempt any three of the following")

        if start == -1:
            return []

        end = text.find(
            "Attempt any one part of the following",
            start
        )

        if end == -1:
            end = len(text)

        section_text = text[start:end]

        section_text = re.sub(
            r"(?m)^a\s+[-—_]+\s*",
            "a. ",
            section_text
        )

        section_text = re.sub(
            r"(?m)^[©]\s*[.)]?\s*",
            "c. ",
            section_text
        )

        section_text = re.sub(
            r"(?m)^[€]\s*[.)]?\s*",
            "e. ",
            section_text
        )

        questions = extract_marked_questions(section_text)

        return [
            q for q in questions
            if q["marker"] in "abcde"
        ][:5]

    match = re.search(
        r"SECTION[- ]?B(.*?)(?=SECTION[- ]?C|$)",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if match:
        return extract_marked_questions(match.group(1))[:5]

    return []


# ============================================================
# FIND SECTION-C BLOCKS
# ============================================================

def find_c_blocks(text):
    pattern = r"Attempt any one part of the following"

    positions = [
        match.start()
        for match in re.finditer(pattern, text, re.IGNORECASE)
    ]

    blocks = []

    for i, start in enumerate(positions):
        end = (
            positions[i + 1]
            if i + 1 < len(positions)
            else len(text)
        )
        blocks.append(text[start:end])

    return blocks[:5]


# ============================================================
# EXTRACT SECTION-C ALTERNATIVES
# ============================================================

def extract_c_alternatives(block):
    lines = [
        line.strip()
        for line in block.splitlines()
        if line.strip()
    ]

    alternatives = []
    current_marker = None
    current_text = []

    marker_patterns = [
        (r"^(?:\(a\)|a\.)", "a"),
        (r"^(?:\(b\)|b\.)", "b"),
        (r"^\(6\)", "b"),
        (r"^\(>\)", "b"),
    ]

    for line in lines:
        found_marker = None
        marker_pattern = None

        for pattern, marker in marker_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                found_marker = marker
                marker_pattern = pattern
                break

        if found_marker:
            if current_marker is not None:
                question = normalize_text(" ".join(current_text))
                if question:
                    alternatives.append({
                        "marker": current_marker,
                        "question": question
                    })

            current_marker = found_marker
            current_text = [
                re.sub(
                    marker_pattern + r"\s*",
                    "",
                    line,
                    count=1,
                    flags=re.IGNORECASE
                )
            ]

        elif current_marker is not None:
            current_text.append(line)

    if current_marker is not None:
        question = normalize_text(" ".join(current_text))
        if question:
            alternatives.append({
                "marker": current_marker,
                "question": question
            })

    return alternatives[:2]


# ============================================================
# SECTION C
# ============================================================

def extract_section_c(text):
    blocks = find_c_blocks(text)
    result = []

    for question_number, block in enumerate(blocks, start=3):
        alternatives = extract_c_alternatives(block)

        result.append({
            "question_number": question_number,
            "alternatives": alternatives
        })

    return result


# ============================================================
# PROCESS ONE FILE
# ============================================================

def process_file(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        text = file.read()

    filename = Path(file_path).name
    text = normalize_text(text)

    return {
        "section_a": extract_section_a(text, filename),
        "section_b": extract_section_b(text, filename),
        "section_c": extract_section_c(text)
    }


# ============================================================
# PROCESS ALL FILES
# ============================================================

def process_all():
    input_dir = Path("data/processed")
    output_file = input_dir / "questions.json"

    cleaned_files = sorted(input_dir.glob("*_cleaned.txt"))

    if not cleaned_files:
        print("No cleaned files found.")
        return

    all_data = {}
    grand_total = 0

    print("\n" + "=" * 70)
    print("QUESTION EXTRACTION")
    print("=" * 70)

    for file_path in cleaned_files:
        print("\n" + "=" * 60)
        print(f"Processing: {file_path.name}")
        print("=" * 60)

        data = process_file(file_path)
        all_data[file_path.stem] = data

        a_count = len(data["section_a"])
        b_count = len(data["section_b"])
        c_count = sum(
            len(question["alternatives"])
            for question in data["section_c"]
        )

        total = a_count + b_count + c_count
        grand_total += total

        print(f"  Section A: {a_count} questions")
        print(f"  Section B: {b_count} questions")
        print(f"  Section C: {len(data['section_c'])} main questions")

        for question in data["section_c"]:
            print(
                f"    Q{question['question_number']} -> "
                f"{len(question['alternatives'])} alternatives"
            )

        print(f"  TOTAL: {total}")

    print("\n" + "=" * 70)
    print("EXTRACTION SUMMARY")
    print("=" * 70)

    for name, data in all_data.items():
        a_count = len(data["section_a"])
        b_count = len(data["section_b"])
        c_count = sum(
            len(question["alternatives"])
            for question in data["section_c"]
        )

        print(
            f"{name}: A={a_count}, B={b_count}, "
            f"C={c_count}, TOTAL={a_count + b_count + c_count}"
        )

    print("-" * 70)
    print(f"TOTAL: {grand_total}")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(
            all_data,
            file,
            indent=2,
            ensure_ascii=False
        )

    print(f"\nSaved: {output_file}")
    print("\nQuestion extraction completed.")


if __name__ == "__main__":
    process_all()
