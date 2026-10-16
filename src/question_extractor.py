import json
import re
from pathlib import Path


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text):
    replacements = {
        "Â©": "(c)",
        "Â¢": "(e)",
        "â‚¬": "(e)",
        "â€“": "-",
        "â€”": "-",
        "â€™": "'",
        "â€œ": '"',
        "â€": '"',
        "Ã—": "x",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


# ============================================================
# GENERIC QUESTION MARKER
# ============================================================

def get_marker(line):
    line = line.strip()

    # (a), (b), (c)...
    match = re.match(r"^\(([a-zA-Z])\)\s*", line)
    if match:
        return match.group(1).lower()

    # a. / a) / a:
    match = re.match(r"^([a-zA-Z])[\.\):]\s*", line)
    if match:
        return match.group(1).lower()

    # OCR: (6) -> (b)
    if re.match(r"^\(6\)\s*", line):
        return "b"

    # OCR: (>) -> (b)
    if re.match(r"^\(>\)\s*", line):
        return "b"

    return None


def remove_marker(line):
    line = re.sub(
        r"^\([a-zA-Z]\)\s*",
        "",
        line
    )

    line = re.sub(
        r"^\([6>]\)\s*",
        "",
        line
    )

    line = re.sub(
        r"^[a-zA-Z][\.\):]\s*",
        "",
        line
    )

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

                question = " ".join(
                    current_text
                ).strip()

                if question:
                    questions.append({
                        "marker": current_marker,
                        "question": question
                    })

            current_marker = marker
            current_text = [
                remove_marker(line)
            ]

        else:

            if current_marker is not None:
                current_text.append(line)

    if current_marker is not None:

        question = " ".join(
            current_text
        ).strip()

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

    # --------------------------------------------------------
    # SPECIAL HANDLING FOR o18-19
    # --------------------------------------------------------

    if filename.startswith("o18-19"):

        start = text.find("SECTION A")

        end = text.find(
            "Attempt any three of the following"
        )

        if start == -1 or end == -1:
            return []

        section_text = text[start:end]
        section_text = re.sub(
            r"(?m)^a\s+[-—_]+\s*",
            "a. ",
            section_text
        )
        section_text = re.sub(
            r"(?m)^¢[.)]\s*",
            "e. ",
            section_text
        )
        section_text = re.sub(
            r"(?m)^f,\s*",
            "f. ",
            section_text
        )

        questions = extract_marked_questions(
            section_text
        )

        fixed = []

        for q in questions:

            # OCR merged E + F into one question
            if q["marker"] == "e":

                question = q["question"]

                # Exact OCR pattern:
                # "... diagram. a PY f, What are..."
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

                    # Second OCR fallback
                    split = re.split(
                        r"\bf\s*,\s*What are",
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
                            "question": (
                                "What are" +
                                split[1]
                            )
                        })

                    else:
                        question = re.sub(
                            r"\s+a\s+PY\s*$",
                            "",
                            question,
                            flags=re.IGNORECASE
                        )
                        fixed.append({
                            "marker": q["marker"],
                            "question": question
                        })

            else:
                fixed.append(q)

        # Section A should contain a-g
        return [
            q for q in fixed
            if q["marker"] in [
                "a",
                "b",
                "c",
                "d",
                "e",
                "f",
                "g"
            ]
        ][:7]

    # --------------------------------------------------------
    # NORMAL PAPERS
    # --------------------------------------------------------

    match = re.search(
        r"SECTION[- ]?A(.*?)(?=SECTION[- ]?B|SECTION[- ]?C|$)",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if match:

        return extract_marked_questions(
            match.group(1)
        )

    return []


# ============================================================
# SECTION B
# ============================================================

def extract_section_b(text, filename):

    # --------------------------------------------------------
    # SPECIAL HANDLING FOR o18-19
    # --------------------------------------------------------

    if filename.startswith("o18-19"):

        start = text.find(
            "Attempt any three of the following"
        )

        end = text.find(
            "Attempt any one part of the following",
            start
        )

        if start == -1:
            return []

        if end == -1:
            end = len(text)

        section_text = text[start:end]
        section_text = re.sub(
            r"(?m)^a\s+[-—_]+\s*",
            "a. ",
            section_text
        )
        section_text = re.sub(
            r"(?m)^©[.)]\s*",
            "c. ",
            section_text
        )
        section_text = re.sub(
            r"(?m)^€[.)]\s*",
            "e. ",
            section_text
        )

        questions = extract_marked_questions(
            section_text
        )

        valid = []

        for q in questions:

            if q["marker"] in [
                "a",
                "b",
                "c",
                "d",
                "e"
            ]:
                valid.append(q)

        return valid[:5]

    # --------------------------------------------------------
    # NORMAL PAPERS
    # --------------------------------------------------------

    match = re.search(
        r"SECTION[- ]?B(.*?)(?=SECTION[- ]?C|$)",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if match:

        return extract_marked_questions(
            match.group(1)
        )[:5]

    return []


# ============================================================
# FIND SECTION-C BLOCKS
# ============================================================

def find_c_blocks(text):

    pattern = (
        r"Attempt any one part of the following"
    )

    positions = [
        m.start()
        for m in re.finditer(
            pattern,
            text,
            re.IGNORECASE
        )
    ]

    blocks = []

    for i, start in enumerate(positions):

        if i + 1 < len(positions):
            end = positions[i + 1]
        else:
            end = len(text)

        blocks.append(
            text[start:end]
        )

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

    for line in lines:

        # ====================================================
        # (a)
        # ====================================================

        if re.match(
            r"^(?:\(a\)|a\.)",
            line,
            re.IGNORECASE
        ):

            if current_marker is not None:

                alternatives.append({
                    "marker": current_marker,
                    "question": " ".join(
                        current_text
                    ).strip()
                })

            current_marker = "a"

            current_text = [
                re.sub(
                    r"^(?:\(a\)|a\.)\s*",
                    "",
                    line,
                    flags=re.IGNORECASE
                )
            ]

            continue

        # ====================================================
        # (b)
        # ====================================================

        if re.match(
            r"^(?:\(b\)|b\.)",
            line,
            re.IGNORECASE
        ):

            if current_marker is not None:

                alternatives.append({
                    "marker": current_marker,
                    "question": " ".join(
                        current_text
                    ).strip()
                })

            current_marker = "b"

            current_text = [
                re.sub(
                    r"^(?:\(b\)|b\.)\s*",
                    "",
                    line,
                    flags=re.IGNORECASE
                )
            ]

            continue

        # ====================================================
        # OCR (6) -> (b)
        # ====================================================

        if re.match(
            r"^\(6\)",
            line
        ):

            if current_marker is not None:

                alternatives.append({
                    "marker": current_marker,
                    "question": " ".join(
                        current_text
                    ).strip()
                })

            current_marker = "b"

            current_text = [
                re.sub(
                    r"^\(6\)\s*",
                    "",
                    line
                )
            ]

            continue

        # ====================================================
        # OCR (>) -> (b)
        # ====================================================

        if re.match(
            r"^\(>\)",
            line
        ):

            if current_marker is not None:

                alternatives.append({
                    "marker": current_marker,
                    "question": " ".join(
                        current_text
                    ).strip()
                })

            current_marker = "b"

            current_text = [
                re.sub(
                    r"^\(>\)\s*",
                    "",
                    line
                )
            ]

            continue

        # ====================================================
        # QUESTION TEXT
        # ====================================================

        if current_marker is not None:
            current_text.append(line)

    # Save final alternative
    if current_marker is not None:

        alternatives.append({
            "marker": current_marker,
            "question": " ".join(
                current_text
            ).strip()
        })

    return alternatives[:2]


# ============================================================
# SECTION C
# ============================================================

def extract_section_c(text):

    blocks = find_c_blocks(text)

    result = []

    for question_number, block in enumerate(
        blocks,
        start=3
    ):

        alternatives = extract_c_alternatives(
            block
        )

        result.append({
            "question_number": question_number,
            "alternatives": alternatives
        })

    return result


# ============================================================
# PROCESS ONE FILE
# ============================================================

def process_file(file_path):

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as file:

        text = file.read()

    filename = Path(file_path).name

    text = normalize_text(text)

    section_a = extract_section_a(
        text,
        filename
    )

    section_b = extract_section_b(
        text,
        filename
    )

    section_c = extract_section_c(
        text
    )

    return {
        "section_a": section_a,
        "section_b": section_b,
        "section_c": section_c
    }


# ============================================================
# PROCESS ALL FILES
# ============================================================

def process_all():

    input_dir = Path(
        "data/processed"
    )

    output_file = Path(
        "data/processed/questions.json"
    )

    cleaned_files = sorted(
        input_dir.glob("*_cleaned.txt")
    )

    if not cleaned_files:

        print(
            "No cleaned files found."
        )

        return

    all_data = {}

    print("\n" + "=" * 70)
    print("QUESTION EXTRACTION")
    print("=" * 70)

    grand_total = 0

    for file_path in cleaned_files:

        print("\n" + "=" * 60)
        print(
            f"Processing: {file_path.name}"
        )
        print("=" * 60)

        data = process_file(
            file_path
        )

        all_data[
            file_path.stem
        ] = data

        a_count = len(
            data["section_a"]
        )

        b_count = len(
            data["section_b"]
        )

        c_count = sum(
            len(q["alternatives"])
            for q in data["section_c"]
        )

        total = (
            a_count +
            b_count +
            c_count
        )

        grand_total += total

        print(
            f"  Section A: "
            f"{a_count} questions"
        )

        print(
            f"  Section B: "
            f"{b_count} questions"
        )

        print(
            f"    Found Section-C blocks: "
            f"{len(data['section_c'])}"
        )

        print(
            f"  Section C: "
            f"{len(data['section_c'])} main questions"
        )

        for q in data["section_c"]:

            print(
                f"    Q{q['question_number']} "
                f"-> "
                f"{len(q['alternatives'])} "
                f"alternatives"
            )

        print(
            f"  TOTAL: {total}"
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    print("\n" + "=" * 70)
    print("EXTRACTION SUMMARY")
    print("=" * 70)

    for name, data in all_data.items():

        a = len(
            data["section_a"]
        )

        b = len(
            data["section_b"]
        )

        c = sum(
            len(q["alternatives"])
            for q in data["section_c"]
        )

        print(
            f"{name}: "
            f"A={a}, "
            f"B={b}, "
            f"C={c}, "
            f"TOTAL={a + b + c}"
        )

    print("-" * 70)
    print(
        f"TOTAL: {grand_total}"
    )

    # ========================================================
    # SAVE JSON
    # ========================================================

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            all_data,
            file,
            indent=2,
            ensure_ascii=False
        )

    print(
        f"\nSaved: {output_file}"
    )

    print(
        "\nQuestion extraction completed."
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    process_all()