from __future__ import annotations

from pathlib import Path

try:
    import pdfplumber
except ImportError:  # pragma: no cover - dependency is optional in tests
    pdfplumber = None


def extract_pdf_text(path: str | Path) -> str:
    if pdfplumber is None:
        msg = "pdfplumber is required for PDF extraction"
        raise RuntimeError(msg)

    with pdfplumber.open(path) as pdf:
        return "\n".join((page.extract_text() or "").strip() for page in pdf.pages).strip()
