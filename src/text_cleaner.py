import re
from pathlib import Path


def clean_text(text):
    """
    Clean extracted raw PDF text.
    """

    # Normalize line endings
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Replace tabs with spaces
    text = text.replace("\t", " ")

    # Remove excessive spaces
    text = re.sub(r" {2,}", " ", text)

    # Remove form-feed/page-break characters
    text = text.replace("\f", "\n")

    # Remove excessive blank lines
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    # Remove spaces at beginning/end of every line
    lines = []

    for line in text.splitlines():
        line = line.strip()

        if line:
            lines.append(line)

    text = "\n".join(lines)

    return text.strip()


def process_raw_files(
    input_dir="data/processed",
    output_dir="data/processed"
):
    """
    Read *_raw.txt files and create *_cleaned.txt files.
    """

    input_path = Path(input_dir)
    output_path = Path(output_dir)

    output_path.mkdir(
        parents=True,
        exist_ok=True
    )

    raw_files = sorted(
        input_path.glob("*_raw.txt")
    )

    if not raw_files:
        print("No raw text files found.")
        print(f"Check folder: {input_path}")
        return

    for raw_file in raw_files:

        print(f"\nCleaning: {raw_file.name}")

        # Read raw text
        with open(
            raw_file,
            "r",
            encoding="utf-8"
        ) as file:

            raw_text = file.read()

        # Clean text
        cleaned_text = clean_text(raw_text)

        # Create cleaned filename
        output_file = output_path / (
            raw_file.stem.replace(
                "_raw",
                ""
            ) + "_cleaned.txt"
        )

        # Save cleaned text
        with open(
            output_file,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(cleaned_text)

        print(
            f"Saved: {output_file}"
        )

        print(
            f"Characters: "
            f"{len(cleaned_text)}"
        )


if __name__ == "__main__":

    process_raw_files()

    print("\nText cleaning completed.")