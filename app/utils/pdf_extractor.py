import fitz  # PyMuPDF

from app.utils.logger import setup_logger

logger = setup_logger(__name__)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract semua text dari PDF (native text, bukan OCR gambar)."""
    text_parts = []

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text()
            if page_text.strip():
                text_parts.append(page_text)
            else:
                logger.warning(f"Page {page_num} has no extractable text (might be scanned/image)")

    full_text = "\n".join(text_parts).strip()

    if not full_text:
        raise ValueError("No text could be extracted from PDF")

    return full_text