"""
Restore ARIA's evidence base into Qdrant from a local ChromaDB snapshot.

IMPORTANT: this does NOT re-embed anything and does not touch the source
PDFs. It reads vectors that already exist in a ChromaDB directory and
uploads them as-is, so a full restore takes minutes rather than the hours
an ingestion run would.

This is the recovery path for a lost Qdrant cluster — the free tier removes
inactive clusters, and when that happened every consultation failed because
retrieval is a hard dependency.

Usage (from the project root):

    # 1. unpack the snapshot, if it is still a tarball
    tar -xzf ~/Desktop/aria_chroma_db_backup.tar.gz -C vectorstore/

    # 2. point .env at the NEW cluster (QDRANT_URL / QDRANT_API_KEY), then
    python migrate_to_qdrant.py

    # resume an interrupted run, or check an existing collection
    python migrate_to_qdrant.py --verify-only
    python migrate_to_qdrant.py --chroma-path /path/to/chroma_db
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid

import chromadb
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

DEFAULT_CHROMA_PATH = "vectorstore/chroma_db"
DEFAULT_COLLECTION = "aria_medical"
VECTOR_SIZE = 384        # all-MiniLM-L6-v2 output dimension
BATCH_SIZE = 500         # upload in small batches to keep memory low


def to_qdrant_id(chroma_id: str) -> str:
    """Qdrant only accepts UUIDs or integers as point IDs.

    Chroma IDs are usually UUIDs already, so we pass them through.
    If one isn't, we derive a stable UUID from it (same input always
    gives the same UUID, so re-running the script never duplicates).
    """
    try:
        return str(uuid.UUID(chroma_id))
    except ValueError:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, chroma_id))


def connect(collection: str) -> QdrantClient:
    load_dotenv()
    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")
    if not url:
        sys.exit("QDRANT_URL is not set. Put the new cluster's URL in .env first.")
    # A local Qdrant needs no key; Qdrant Cloud always does.
    print(f"Connecting to {url} (collection: {collection})")
    return QdrantClient(url=url, api_key=api_key or None, timeout=120)


def verify(qdrant: QdrantClient, collection: str, expected: int | None = None) -> bool:
    """Report what the target collection actually holds.

    Checks the two things that silently produce a broken-but-'present'
    store: the wrong vector dimension (a collection built with a different
    embedding model returns nonsense rather than erroring) and a partial
    upload.
    """
    if not qdrant.collection_exists(collection):
        print(f"FAIL: collection {collection!r} does not exist")
        return False

    info = qdrant.get_collection(collection)
    count = qdrant.count(collection).count
    size = info.config.params.vectors.size

    print(f"  points      : {count}")
    print(f"  vector size : {size}")

    ok = True
    if size != VECTOR_SIZE:
        print(f"FAIL: expected {VECTOR_SIZE}-dimensional vectors (all-MiniLM-L6-v2)")
        ok = False
    if count == 0:
        print("FAIL: collection is empty — it cannot ground any answer")
        ok = False
    if expected is not None and count != expected:
        print(f"WARNING: expected {expected} points — re-run to fill the gaps")
        ok = False

    # Provenance: both books must survive the restore, or the source-balanced
    # retriever silently degrades to a single-book system.
    if ok:
        rx = qdrant.count(
            collection,
            count_filter={"must": [{"key": "metadata.book", "match": {"value": "rxprep"}}]},
        ).count
        print(f"  RxPrep      : {rx}")
        print(f"  DiPiro      : {count - rx}")
        if rx == 0:
            print("WARNING: no RxPrep chunks — the RxPrep half of the corpus is missing")

    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chroma-path", default=DEFAULT_CHROMA_PATH)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="check the target collection without uploading anything",
    )
    args = parser.parse_args()

    if args.verify_only:
        qdrant = connect(args.collection)
        print("\n── Verifying ──")
        sys.exit(0 if verify(qdrant, args.collection) else 1)

    if not os.path.isdir(args.chroma_path):
        sys.exit(
            f"No ChromaDB at {args.chroma_path!r}.\n"
            "Unpack the snapshot first, e.g.\n"
            "  tar -xzf ~/Desktop/aria_chroma_db_backup.tar.gz -C vectorstore/"
        )

    print(f"Opening ChromaDB at: {args.chroma_path}")
    chroma_client = chromadb.PersistentClient(path=args.chroma_path)
    # LangChain stores everything in a collection called "langchain"
    chroma_collection = chroma_client.get_collection("langchain")
    total = chroma_collection.count()
    print(f"Found {total} chunks to restore")

    qdrant = connect(args.collection)

    # Create the collection if absent, so the script is safe to re-run after
    # an interruption.
    if not qdrant.collection_exists(args.collection):
        qdrant.create_collection(
            collection_name=args.collection,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"Created collection: {args.collection}")
    else:
        print(f"Collection {args.collection!r} already exists — resuming upload")

    uploaded = 0
    while uploaded < total:
        batch = chroma_collection.get(
            limit=BATCH_SIZE,
            offset=uploaded,
            include=["embeddings", "documents", "metadatas"],
        )

        # The payload layout ("page_content" + "metadata") is exactly what
        # langchain-qdrant expects, so retrieval works unchanged.
        points = [
            PointStruct(
                id=to_qdrant_id(chroma_id),
                vector=embedding.tolist(),
                payload={"page_content": text, "metadata": metadata},
            )
            for chroma_id, embedding, text, metadata in zip(
                batch["ids"],
                batch["embeddings"],
                batch["documents"],
                batch["metadatas"],
            )
        ]
        if not points:
            break

        # wait=True means Qdrant confirms the batch is stored before continuing
        qdrant.upsert(collection_name=args.collection, points=points, wait=True)

        uploaded += len(points)
        print(f"Uploaded {uploaded}/{total} ({uploaded / total * 100:.1f}%)")

    print("\n── Verifying ──")
    if verify(qdrant, args.collection, expected=total):
        print("\nRestore successful. Set the same QDRANT_URL / QDRANT_API_KEY")
        print("as secrets on the Hugging Face Space, then restart it.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
