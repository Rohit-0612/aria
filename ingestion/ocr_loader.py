"""
OCR loader for scanned, image-only PDFs (e.g. the RxPrep NAPLEX course book).

The RxPrep PDF has no text layer — every page is a scanned image — so the
normal PyPDFLoader returns nothing. Here we rasterize each page with PyMuPDF
and run Tesseract OCR, in parallel across CPU cores, then clean and quality-gate
the text and return LangChain Documents carrying source/book/page provenance.
"""

import os
import re
import shutil
import io
from multiprocessing import get_context

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from langchain_core.documents import Document

# Point pytesseract at the Homebrew binary if it isn't already on PATH.
_TESS = shutil.which("tesseract") or "/opt/homebrew/bin/tesseract"
if os.path.exists(_TESS):
    pytesseract.pytesseract.tesseract_cmd = _TESS

# --- Cleaning ---------------------------------------------------------------

WATERMARK = re.compile(r"alg?rawany", re.IGNORECASE)


def clean_ocr_text(text: str) -> str:
    """Normalise raw OCR output from a scanned book page."""
    text = WATERMARK.sub(" ", text)
    # Re-join words split across a line break by hyphenation.
    text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)
    # Drop lines that are just a page number.
    text = re.sub(r"\n\s*\d{1,4}\s*\n", "\n", text)
    text = text.replace("\r", " ")
    # Collapse intra-line whitespace but keep paragraph breaks for the splitter.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip stray non-ASCII OCR artifacts (consistent with the DiPiro pipeline).
    text = re.sub(r"[^\x00-\x7F]+", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def is_useful_page(text: str) -> bool:
    """Reject blank scans, dividers, and OCR garbage (mostly non-letters)."""
    if len(text) < 150:
        return False
    letters = sum(c.isalpha() for c in text)
    if letters / len(text) < 0.45:
        return False
    return True


# --- Parallel OCR -----------------------------------------------------------

_DOC = None
_DPI = 300


def _init_worker(path: str, dpi: int):
    global _DOC, _DPI
    _DOC = fitz.open(path)
    _DPI = dpi


def _ocr_page(i: int):
    page = _DOC[i]
    pix = page.get_pixmap(dpi=_DPI)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    if img.mode != "L":
        img = img.convert("L")  # grayscale helps Tesseract a little
    raw = pytesseract.image_to_string(img)
    return i, raw


def ocr_pdf(
    path: str,
    source: str,
    book: str,
    dpi: int = 300,
    start: int = 0,
    limit: int | None = None,
    workers: int | None = None,
    progress_every: int = 25,
) -> list[Document]:
    """OCR a scanned PDF into cleaned, provenance-tagged Documents."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    with fitz.open(path) as probe:
        total = probe.page_count
    end = total if limit is None else min(total, start + limit)
    indices = list(range(start, end))
    workers = workers or max(1, (os.cpu_count() or 4) - 1)

    print(f"OCR: {path}")
    print(f"  pages {start}–{end - 1} of {total} · dpi={dpi} · workers={workers}")

    docs: list[Document] = []
    kept = skipped = 0
    ctx = get_context("spawn")
    with ctx.Pool(workers, initializer=_init_worker, initargs=(path, dpi)) as pool:
        for n, (i, raw) in enumerate(
            pool.imap_unordered(_ocr_page, indices, chunksize=2), start=1
        ):
            text = clean_ocr_text(raw)
            if is_useful_page(text):
                docs.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": source,
                            "book": book,
                            "page": i + 1,        # human 1-indexed page
                            "pdf_index": i,
                        },
                    )
                )
                kept += 1
            else:
                skipped += 1
            if n % progress_every == 0 or n == len(indices):
                print(f"  …{n}/{len(indices)} OCR'd · kept {kept} · skipped {skipped}", flush=True)

    docs.sort(key=lambda d: d.metadata["pdf_index"])
    print(f"OCR complete: {kept} useful pages, {skipped} skipped.")
    return docs


if __name__ == "__main__":
    sample = ocr_pdf(
        "data/Rxprep Uworld 2025 NAPLEX Course Book ALGrawany-1.pdf",
        source="RxPrep NAPLEX Course Book (2025)",
        book="rxprep",
        start=100,
        limit=4,
    )
    for d in sample:
        print(f"\n--- page {d.metadata['page']} ({len(d.page_content)} chars) ---")
        print(d.page_content[:300])
