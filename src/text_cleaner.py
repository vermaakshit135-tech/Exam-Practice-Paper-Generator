
import re
import unicodedata
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"


def fix_encoding(text):
    """Fix common mojibake while preserving valid Unicode."""

    replacements = {
        "â€™": "'",
        "â€˜": "'",
        "â€œ": '"',
        "â€\x9d": '"',
        "â€“": "-",
        "â€”": "-",
        "â€¦": "...",
        "Ã—": "x",
        "Â°": " degrees ",
        "\ufffd": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Normalize valid punctuation.
    text = text.replace("’", "'")
    text = text.replace("‘", "'")
    text = text.replace("“", '"')
    text = text.replace("”", '"')
    text = text.replace("–", "-")
    text = text.replace("—", "-")

    return text.replace("Â", "")


def clean_text(text):
    text = unicodedata.normalize("NFC", text)
    text = fix_encoding(text)

    # Normalize line endings.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    cleaned_lines = []

    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()

        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def process_files():
    if not DATA_DIR.exists():
        print(f"Directory not found: {DATA_DIR}")
        return

    raw_files = sorted(DATA_DIR.glob("*_raw.txt"))

    if not raw_files:
        print(f"No raw text files found in: {DATA_DIR}")
        return

    for input_file in raw_files:
        output_file = DATA_DIR / input_file.name.replace(
            "_raw.txt",
            "_cleaned.txt"
        )

        text = input_file.read_text(
            encoding="utf-8",
            errors="replace"
        )

        cleaned = clean_text(text)

        output_file.write_text(
            cleaned,
            encoding="utf-8"
        )

        print(
            f"Cleaned: {input_file.name} -> "
            f"{output_file.name} ({len(cleaned)} characters)"
        )

    print("\nText cleaning completed.")


if __name__ == "__main__":
    process_files()
