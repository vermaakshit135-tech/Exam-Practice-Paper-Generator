import pymupdf
import pytesseract

from PIL import Image
from pathlib import Path
from io import BytesIO


# ============================================================
# TESSERACT CONFIGURATION
# ============================================================

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


# ============================================================
# OCR FUNCTION
# ============================================================

def extract_page_with_ocr(page):
    """
    Convert a PDF page into an image
    and extract text using Tesseract OCR.
    """

    # Increase resolution for better OCR accuracy
    pix = page.get_pixmap(
        matrix=pymupdf.Matrix(2, 2)
    )

    # Convert PDF image bytes into PIL Image
    image = Image.open(
        BytesIO(
            pix.tobytes("png")
        )
    )

    # OCR
    text = pytesseract.image_to_string(
        image
    )

    return text


# ============================================================
# PDF TEXT EXTRACTION
# ============================================================

def extract_text(pdf_path):
    """
    Extract text from a PDF page by page.

    First:
        PyMuPDF normal text extraction

    If no text is found:
        Tesseract OCR
    """

    pages = []

    with pymupdf.open(pdf_path) as docs:

        for page_number, page in enumerate(
            docs,
            start=1
        ):

            # --------------------------------------------
            # Try normal PDF text extraction
            # --------------------------------------------

            text = page.get_text().strip()

            if text:

                print(
                    f"  Page {page_number}: "
                    f"normal text extraction"
                )

            # --------------------------------------------
            # If no text -> OCR
            # --------------------------------------------

            else:

                print(
                    f"  Page {page_number}: "
                    f"OCR required"
                )

                text = extract_page_with_ocr(
                    page
                )

            pages.append(text)

    return pages


# ============================================================
# PROCESS ALL PDFs
# ============================================================

def parse_all(input_dir="data/pdf"):
    """
    Process all PDF files inside data/pdf.
    """

    result = {}

    pdf_dir = Path(input_dir)

    # Check folder
    if not pdf_dir.exists():

        print(
            f"PDF folder not found: {pdf_dir}"
        )

        return result

    # Find PDFs
    pdf_files = sorted(
        pdf_dir.glob("*.pdf")
    )

    if not pdf_files:

        print(
            f"No PDF files found in: {pdf_dir}"
        )

        return result

    # Process every PDF
    for pdf in pdf_files:

        print(
            f"\nProcessing: {pdf.name}"
        )

        pages = extract_text(
            pdf
        )

        result[pdf.name] = pages

    return result


# ============================================================
# SAVE RAW TEXT
# ============================================================

def save_raw_text(
    data,
    output_dir="data/processed"
):
    """
    Save extracted text of every PDF
    into *_raw.txt files.
    """

    output_path = Path(
        output_dir
    )

    output_path.mkdir(
        parents=True,
        exist_ok=True
    )

    for pdf_name, pages in data.items():

        # Example:
        # o18-19.pdf
        # ->
        # o18-19_raw.txt

        txt_name = (
            Path(pdf_name).stem
            + "_raw.txt"
        )

        file_path = (
            output_path / txt_name
        )

        # Write text
        with open(
            file_path,
            "w",
            encoding="utf-8"
        ) as file:

            for page_number, text in enumerate(
                pages,
                start=1
            ):

                # Page separator
                file.write(
                    f"\n===== PAGE {page_number} =====\n\n"
                )

                file.write(
                    text
                )

                file.write(
                    "\n"
                )

        # Character count
        total_chars = sum(
            len(page)
            for page in pages
        )

        print(
            f"Saved: {file_path} "
            f"({total_chars} characters)"
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------
    # Step 1: Extract all PDFs
    # --------------------------------------------

    data = parse_all()

    # --------------------------------------------
    # Step 2: Show summary
    # --------------------------------------------

    print(
        "\n" + "=" * 60
    )

    print(
        "PDF PARSER SUMMARY"
    )

    print(
        "=" * 60
    )

    for name, pages in data.items():

        total = sum(
            len(page)
            for page in pages
        )

        print(
            f"{name}: "
            f"{len(pages)} pages, "
            f"{total} characters"
        )

    # --------------------------------------------
    # Step 3: Save extracted text
    # --------------------------------------------

    print(
        "\nSaving raw extracted text..."
    )

    save_raw_text(
        data
    )

    # --------------------------------------------
    # Done
    # --------------------------------------------

    print(
        "\nPDF parsing completed."
    )