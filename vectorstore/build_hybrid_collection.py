"""
Build `aria_medical_v2`: the evidence base with dense AND sparse (BM25)
vectors, and without the reference matter that was polluting retrieval.

    aria_env/bin/python -m vectorstore.build_hybrid_collection

Nothing is re-embedded. The 384-d dense vectors are copied from the existing
collection as they are; only the BM25 sparse vectors are computed, and BM25
is word counting, not a neural model — the whole corpus takes about a minute
of light CPU work. The source collection is read, never written, so the live
app keeps serving from it until the switch is made deliberately.

What changes between the collections:

  * sparse "bm25" vectors beside the dense ones, with Qdrant applying IDF
    server-side, so hybrid search can match exact drug names that dense
    embeddings blur together (sitagliptin vs. vildagliptin);
  * chapter bibliographies and back-of-book index pages are left out
    (they were filtered at query time; with BM25 they would rank even
    higher, because a reference list contains every keyword);
  * the payload keeps what citations need — text, book, PDF page and the
    printed page label — and drops the per-chunk PDF metadata (author
    list, producer, copyright notice) that was repeated 31,000 times.

Re-running is safe: point IDs are preserved, so upserts overwrite.
"""

from __future__ import annotations

import argparse
import logging
import time
from typing import Any

from dotenv import load_dotenv
from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient, models

from retrieval.reranker import is_reference_matter
from vectorstore.qdrant_store import (
    BM25_MODEL,
    DENSE_VECTOR,
    LEGACY_COLLECTION,
    SPARSE_VECTOR,
    get_client,
)

logger = logging.getLogger("aria.build_hybrid")

TARGET = "aria_medical_v2"  # == qdrant_store.COLLECTION_NAME
DENSE = DENSE_VECTOR
SPARSE = SPARSE_VECTOR
BATCH = 256
#: A breath between batches: keeps the laptop cool and stays well inside
#: the free cluster's write rate.
PAUSE_S = 0.3


def slim_payload(payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload.get("metadata") or {}
    kept = {
        "book": meta.get("book", "dipiro"),
        "page": meta.get("page"),
        "page_label": meta.get("page_label"),
        "source": meta.get("source"),
    }
    return {
        "page_content": payload.get("page_content", ""),
        "metadata": {k: v for k, v in kept.items() if v is not None},
    }


def create_target(client: QdrantClient, recreate: bool) -> None:
    if client.collection_exists(TARGET):
        if not recreate:
            logger.info("%s exists — upserting into it (pass --recreate to start over)", TARGET)
            return
        client.delete_collection(TARGET)
    client.create_collection(
        TARGET,
        vectors_config={DENSE: models.VectorParams(size=384, distance=models.Distance.COSINE)},
        sparse_vectors_config={SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)},
    )
    client.create_payload_index(TARGET, "metadata.book", models.PayloadSchemaType.KEYWORD)
    logger.info("created %s (dense %s + sparse %s with IDF)", TARGET, DENSE, SPARSE)


def build(source: str, recreate: bool) -> dict[str, int]:
    client = get_client()
    create_target(client, recreate)
    bm25 = SparseTextEmbedding(BM25_MODEL)

    stats = {"read": 0, "written": 0, "bibliography_or_index": 0}
    offset: Any = None
    while True:
        points, offset = client.scroll(
            source, limit=BATCH, offset=offset, with_vectors=True, with_payload=True
        )
        if not points:
            break
        stats["read"] += len(points)

        keep = [p for p in points if not is_reference_matter(str((p.payload or {}).get("page_content", "")))]
        stats["bibliography_or_index"] += len(points) - len(keep)
        if keep:
            texts = [str((p.payload or {})["page_content"]) for p in keep]
            sparse = list(bm25.embed(texts, batch_size=BATCH))
            client.upsert(
                TARGET,
                points=[
                    models.PointStruct(
                        id=p.id,
                        vector={
                            DENSE: p.vector,  # copied, not recomputed
                            SPARSE: models.SparseVector(
                                indices=s.indices.tolist(), values=s.values.tolist()
                            ),
                        },
                        payload=slim_payload(p.payload or {}),
                    )
                    for p, s in zip(keep, sparse, strict=True)
                ],
            )
            stats["written"] += len(keep)

        logger.info(
            "%d read · %d written · %d reference matter dropped",
            stats["read"],
            stats["written"],
            stats["bibliography_or_index"],
        )
        if offset is None:
            break
        time.sleep(PAUSE_S)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=LEGACY_COLLECTION)
    parser.add_argument("--recreate", action="store_true", help="drop and rebuild the target")
    args = parser.parse_args()
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    started = time.time()
    stats = build(args.source, args.recreate)
    count = get_client().count(TARGET, exact=True).count
    logger.info("done in %.0fs: %s · %s now holds %d points", time.time() - started, stats, TARGET, count)


if __name__ == "__main__":
    main()
