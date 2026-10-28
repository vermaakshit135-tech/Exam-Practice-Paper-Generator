
import re
from pathlib import Path
from io import BytesIO

import pymupdf
import pytesseract
from PIL import Image


# Windows par Tesseract OCR ka path
pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


def extract_page_with_ocr(page):
    """Extract page text using OCR."""
    pix = page.get_pixmap(
        matrix=pymupdf.Matrix(2, 2),
        alpha=False
    )

    image = Image.open(BytesIO(pix.tobytes("png")))

    # English OCR
    text = pytesseract.image_to_string(
        image,
        lang="eng",
        config="--psm 3"
    )

    return text.strip()


def is_text_corrupted(text):
    """Detect common OCR and text-extraction corruption."""
    if not text or len(text.strip()) < 30:
        return True

    corruption_patterns = [
        "â€™",
        "â€“",
        "â€œ",
        "â€",
        "Â",
        "Ã",
        "�",
    ]

    if any(pattern in text for pattern in corruption_patterns):
        return True

    # Detect excessive replacement or unusual characters.
    unusual_count = len(re.findall(r"[�]", text))
    if unusual_count >= 2:
        return True

    return False


def extract_text(pdf_path):
    """Extract text from all pages, using OCR when needed."""
    pages = []

    with pymupdf.open(pdf_path) as docs:
        for page_number, page in enumerate(docs, start=1):
            text = page.get_text("text").strip()

            if is_text_corrupted(text):
                print(
                    f"Page {page_number}: "
                    "corrupted/empty text detected; trying OCR"
                )

                ocr_text = extract_page_with_ocr(page)

                # Use OCR only if it returned usable text.
                if ocr_text and len(ocr_text) > len(text) * 0.5:
                    text = ocr_text
                    print(f"Page {page_number}: OCR text selected")
                else:
                    print(
                        f"Page {page_number}: "
                        "OCR result not clearly better; keeping original"
                    )
            else:
                print(f"Page {page_number}: normal text extraction")

            pages.append(text)

    return pages


def parse_all(input_dir="data/pdf"):
    """Parse every PDF in the input directory."""
    pdf_dir = Path(input_dir)

    if not pdf_dir.exists():
        raise FileNotFoundError(
            f"PDF directory not found: {pdf_dir.resolve()}"
        )

    pdf_files = sorted(pdf_dir.glob("*.pdf"))

    if not pdf_files:
        print(f"No PDF files found in {pdf_dir.resolve()}")
        return {}

    result = {}

    for pdf_path in pdf_files:
        print(f"\nProcessing: {pdf_path.name}")
        result[pdf_path.name] = extract_text(pdf_path)

    return result


def save_raw_text(data, output_dir="data/processed"):
    """Save extracted page text into individual raw text files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for pdf_name, pages in data.items():
        txt_name = Path(pdf_name).stem + "_raw.txt"
        output_file = output_path / txt_name

        with open(output_file, "w", encoding="utf-8") as file:
            for page_number, text in enumerate(pages, start=1):
                file.write(f"\n===== PAGE {page_number} =====\n\n")
                file.write(text)
                file.write("\n")

        print(f"Saved: {output_file}")


if __name__ == "__main__":
    extracted_data = parse_all()

    print("\nExtraction Summary")
    print("-" * 40)

    for pdf_name, pages in extracted_data.items():
        total_chars = sum(len(page) for page in pages)
        print(
            f"{pdf_name}: "
            f"{len(pages)} pages, {total_chars} characters"
        )

    save_raw_text(extracted_data)
