"""
Loads the Qdrant Cloud vector store (replacement for chroma_store.py).

The embeddings live in Qdrant Cloud (collection "aria_medical"), so
nothing is stored on disk here. The embedding model is still loaded
locally — it's only used to embed the *query* text at search time.
"""

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from dotenv import load_dotenv
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'ingestion'))
from embedder import load_embedding_model

COLLECTION_NAME = "aria_medical"


def load_vectorstore():
    # Read QDRANT_URL and QDRANT_API_KEY from the project's .env file
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    if not qdrant_url or not qdrant_api_key:
        raise ValueError("QDRANT_URL and QDRANT_API_KEY must be set in .env")

    # Same model as before (all-MiniLM-L6-v2) — queries must be embedded
    # with the same model the documents were embedded with
    embedding_model = load_embedding_model()

    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=60)

    vectorstore = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embedding_model,
    )

    print(f"Qdrant vector store loaded — collection: {COLLECTION_NAME}")

    return vectorstore


if __name__ == "__main__":
    vectorstore = load_vectorstore()

    print("\n── Test Query ──────────────────────")
    results = vectorstore.similarity_search("What is hypertension?", k=3)
    for i, doc in enumerate(results):
        print(f"\nResult {i+1}:")
        print(f"Text: {doc.page_content[:200]}")
        print(f"Page: {doc.metadata.get('page', '?')}")
