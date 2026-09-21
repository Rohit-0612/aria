"""Embedding model loader. The model ID comes from `llm.config`."""

from __future__ import annotations

import logging

from langchain_huggingface import HuggingFaceEmbeddings

from llm.config import embedding_model

logger = logging.getLogger(__name__)

__all__ = ["get_embeddings_for_text", "load_embedding_model"]


def load_embedding_model(model_name: str | None = None) -> HuggingFaceEmbeddings:
    """Load the sentence-transformers embedding model.

    Args:
        model_name: override the configured model. Defaults to
            ARIA_EMBEDDING_MODEL / `all-MiniLM-L6-v2`.
    """
    name = model_name or embedding_model()
    logger.info("Loading embedding model: %s (may download on first run)", name)
    embeddings = HuggingFaceEmbeddings(
        model_name=name,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    logger.info("Embedding model ready")
    return embeddings


def get_embeddings_for_text(text: str, embeddings_model: HuggingFaceEmbeddings) -> list[float]:
    """Embed a single string. Kept for interactive inspection of the store."""
    vector: list[float] = embeddings_model.embed_query(text)
    logger.info("embedded %r -> %d dimensions", text, len(vector))
    return vector


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    model = load_embedding_model()
    a = get_embeddings_for_text("AI chips demand increased", model)
    b = get_embeddings_for_text("GPU sales went up", model)
    c = get_embeddings_for_text("Cricket match was exciting", model)
    print(f"AI/GPU similarity     : {sum(x * y for x, y in zip(a, b, strict=True)):.4f}")
    print(f"AI/cricket similarity : {sum(x * y for x, y in zip(a, c, strict=True)):.4f}")
