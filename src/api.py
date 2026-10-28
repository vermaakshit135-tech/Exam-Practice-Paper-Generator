
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
import traceback


from pdf_parser import extract_text
from question_extractor import extract_section_a


app = FastAPI(
    title="Paper Analyzer API",
    description="AKTU previous-year question paper analyzer",
    version="1.0.0",
)


# Project folders
BASE_DIR = Path(__file__).resolve().parent.parent
PDF_DIR = BASE_DIR / "data" / "pdf"


@app.get("/")
def home():
    return {
        "message": "Paper Analyzer API is running",
        "docs": "/docs",
        "endpoints": [
            "/",
            "/health",
            "/papers",
            "/parse-pdf",
        ],
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Paper Analyzer API",
    }


@app.get("/papers")
def list_papers():
    """List PDF files available in data/input."""

    if not PDF_DIR.exists():
        return {
            "total_papers": 0,
            "papers": [],
            "message": "PDF input folder not found",
        }

    pdf_files = sorted(
        file.name
        for file in PDF_DIR.glob("*.pdf")
    )

    return {
        "total_papers": len(pdf_files),
        "papers": pdf_files,
    }


@app.get("/parse-pdf")
def parse_pdf(
    filename: str = Query(
        ...,
        description="PDF filename available in data/input",
        examples=["o20-21.pdf"],
    )
):
    """Extract text and questions from a PDF."""

    # Accept only a filename, not an arbitrary file path
    if (
        Path(filename).name != filename
        or not filename.lower().endswith(".pdf")
    ):
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid PDF filename.",
        )

    pdf_path = PDF_DIR / filename

    if not pdf_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"PDF file not found: {filename}",
        )

    try:
        # Extract text page by page
        pages = extract_text(pdf_path)

        if not pages:
            raise HTTPException(
                status_code=422,
                detail="No text could be extracted from this PDF.",
            )

        full_text = "\n".join(
            str(page) for page in pages
        )

        
        questions = extract_section_a(full_text)

        return {
            "filename": filename,
            "total_pages": len(pages),
            "total_questions": len(questions),
            "questions": questions,
        }

    except HTTPException:
        raise

    except Exception as exc:
    traceback.print_exc()
    raise HTTPException(
        status_code=500,
        detail=f"Failed to process PDF: {str(exc)}",
    ) from exc