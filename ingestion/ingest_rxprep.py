"""
Ingest the scanned RxPrep NAPLEX course book into ARIA's vector store.

Pipeline:  rasterize + OCR (ocr_loader)  ->  chunk (chunker)  ->  embed & add
to the SAME Chroma collection DiPiro lives in, so retrieval spans both books.
Every chunk keeps source/book/page metadata for citation.

Usage (from project root):
    aria_env/bin/python ingestion/ingest_rxprep.py            # full book
    aria_env/bin/python ingestion/ingest_rxprep.py --limit 20 # quick test
    aria_env/bin/python ingestion/ingest_rxprep.py --dry      # OCR+chunk, no DB write
"""

import sys
import os
import argparse

sys.path.append(os.path.join(os.path.dirname(__file__)))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "vectorstore"))

from ocr_loader import ocr_pdf
from chunker import chunk_documents
from chroma_store import load_vectorstore

PDF = "data/Rxprep Uworld 2025 NAPLEX Course Book ALGrawany-1.pdf"
SOURCE = "RxPrep NAPLEX Course Book (2025)"
BOOK = "rxprep"
PERSIST = "vectorstore/chroma_db"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--dry", action="store_true", help="OCR + chunk only, skip DB write")
    args = ap.parse_args()

    pages = ocr_pdf(PDF, source=SOURCE, book=BOOK, dpi=args.dpi, start=args.start, limit=args.limit)
    if not pages:
        print("No useful pages produced — aborting.")
        return

    chunks = chunk_documents(pages, chunk_size=1000, chunk_overlap=200)
    print(f"\nProduced {len(chunks)} chunks from {len(pages)} pages.")
    print("Sample chunk metadata:", chunks[0].metadata)

    if args.dry:
        print("\n[dry run] Skipping vector store write.")
        return

    print(f"\nLoading vector store at {PERSIST} …")
    vs = load_vectorstore(PERSIST)
    try:
        before = vs._collection.count()
    except Exception:
        before = None
    print(f"  existing vectors: {before}")

    print(f"Embedding & adding {len(chunks)} chunks in batches of {args.batch} …")
    for i in range(0, len(chunks), args.batch):
        batch = chunks[i : i + args.batch]
        vs.add_documents(batch)
        print(f"  added {min(i + args.batch, len(chunks))}/{len(chunks)}", flush=True)

    try:
        after = vs._collection.count()
        print(f"\nDone. Collection now holds {after} vectors (+{after - (before or 0)}).")
    except Exception:
        print("\nDone adding RxPrep chunks.")


if __name__ == "__main__":
    main()
