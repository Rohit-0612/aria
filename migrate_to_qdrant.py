"""
Migrate existing embeddings from local ChromaDB to Qdrant Cloud.

IMPORTANT: This does NOT re-embed anything. It reads the vectors that
already exist in vectorstore/chroma_db and uploads them as-is.

Run from the project root:
    python migrate_to_qdrant.py
"""

import os
import uuid

import chromadb
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

# ── Settings ────────────────────────────────────────────────────────
CHROMA_PATH = "vectorstore/chroma_db"
COLLECTION_NAME = "aria_medical"
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


def main():
    # Step 1: Load Qdrant Cloud credentials from .env
    load_dotenv()
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    if not qdrant_url or not qdrant_api_key:
        raise ValueError("QDRANT_URL and QDRANT_API_KEY must be set in .env")

    # Step 2: Open the local ChromaDB (read-only, no embedding model needed)
    print(f"Opening ChromaDB at: {CHROMA_PATH}")
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    # LangChain stores everything in a collection called "langchain"
    chroma_collection = chroma_client.get_collection("langchain")
    total = chroma_collection.count()
    print(f"Found {total} chunks to migrate")

    # Step 3: Connect to Qdrant Cloud
    print(f"Connecting to Qdrant Cloud...")
    qdrant = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=60)

    # Step 4: Create the collection (skip if it already exists,
    # so the script is safe to re-run after an interruption)
    if not qdrant.collection_exists(COLLECTION_NAME):
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"Created collection: {COLLECTION_NAME}")
    else:
        print(f"Collection '{COLLECTION_NAME}' already exists — resuming upload")

    # Step 5: Read from Chroma and upload to Qdrant, batch by batch
    uploaded = 0
    while uploaded < total:
        # Pull one batch of ids + vectors + texts + metadata from Chroma
        batch = chroma_collection.get(
            limit=BATCH_SIZE,
            offset=uploaded,
            include=["embeddings", "documents", "metadatas"],
        )

        # Convert each record into a Qdrant "point".
        # The payload layout ("page_content" + "metadata") is exactly
        # what langchain-qdrant expects, so retrieval works unchanged.
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

        # wait=True means Qdrant confirms the batch is stored before we continue
        qdrant.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)

        uploaded += len(points)
        percent = uploaded / total * 100
        print(f"Uploaded {uploaded}/{total} ({percent:.1f}%)")

    # Step 6: Verify the final count in Qdrant matches
    qdrant_count = qdrant.count(COLLECTION_NAME).count
    print(f"\nDone! Qdrant collection '{COLLECTION_NAME}' now has {qdrant_count} points")
    if qdrant_count == total:
        print("Counts match — migration successful.")
    else:
        print("Warning: counts don't match — re-run the script to fill gaps.")


if __name__ == "__main__":
    main()
