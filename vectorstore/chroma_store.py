from langchain_chroma import Chroma
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'ingestion'))
from embedder import load_embedding_model


def create_vectorstore(chunks: list, persist_directory: str = "vectorstore/chroma_db"):
    embedding_model = load_embedding_model()

    print(f"\nCreating vector store with {len(chunks)} chunks...")
    print(f"It might take some time")

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        persist_directory=persist_directory
    )

    print(f"Vector store created and saved to: {persist_directory}")

    return vectorstore


def load_vectorstore(persist_directory: str = "vectorstore/chroma_db"):
    if not os.path.exists(persist_directory):
        raise FileNotFoundError(
            f"Could not find the database {persist_directory}. "
            f"Run create_vectorstore() first."
        )

    embedding_model = load_embedding_model()

    vectorstore = Chroma(
        persist_directory=persist_directory,
        embedding_function=embedding_model
    )

    print(f"Vector store loaded from: {persist_directory}")

    return vectorstore


if __name__ == "__main__":
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'ingestion'))
    from pdf_loader import load_and_clean_pdf
    from chunker import chunk_documents

    persist_dir = "vectorstore/chroma_db"

    # Smart logic: database hai toh load, nahi toh create
    if os.path.exists(persist_dir):
        print("Database is already existing — loading...")
        vectorstore = load_vectorstore(persist_dir)
    else:
        print("Database not found — creating databse...")
        pages = load_and_clean_pdf("data/dipiro_raw.pdf")
        chunks = chunk_documents(pages)
        vectorstore = create_vectorstore(chunks)

    print("\n── Test Query ──────────────────────")
    results = vectorstore.similarity_search("What is hypertension?", k=3)
    for i, doc in enumerate(results):
        print(f"\nResult {i+1}:")
        print(f"Text: {doc.page_content[:200]}")
        print(f"Page: {doc.metadata.get('page', '?')}")