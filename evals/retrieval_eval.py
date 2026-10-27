"""
Retrieval eval — does the Navigator find the passage a question came from?

The answer-quality suite scores what the generator did with the passages it
was given; it cannot say whether those were the right passages. This one
isolates retrieval, using the standard synthetic set-up:

  1. sample real passages from the collection, an equal number per book;
  2. have a model write the question each passage answers;
  3. run that question through retrieval and look for its source passage.

Reported per stage, so a miss can be blamed on the right layer:

  * first-stage recall — the global candidate set alone: plain dense search
                       on a dense collection, dense + BM25 fused by RRF on a
                       hybrid one
  * candidate recall — global + the RxPrep-filtered set (what the reranker
                       actually gets to see)
  * hit rate         — the source survives reranking and the relevance
                       floor, i.e. it reaches the generator
  * MRR              — mean reciprocal rank of the source among those kept

A synthetic question is easier than a real one (it shares the passage's
vocabulary), so treat these numbers as an upper bound on retrieval quality,
and compare runs with each other rather than with the outside world.

Run from the project root:
    aria_env/bin/python evals/retrieval_eval.py [--n 24]
Results are saved to evals/retrieval_results.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import UTC, datetime
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant_client import models

from llm.config import Role, rerank_model
from llm.llm_setup import invoke_role
from retrieval.reranker import RXPREP_FILTER, BalancedRetriever, get_balanced_retriever

RXPREP_CONDITION = models.FieldCondition(
    key="metadata.book", match=models.MatchValue(value="rxprep")
)
from vectorstore.qdrant_store import collection_name, get_client

QUESTION_PROMPT = """Below is a passage from a clinical pharmacotherapy textbook.

Write ONE specific question that a pharmacist or clinician might ask, which this passage answers. Use your own words rather than copying a sentence, and do not mention "the passage" or "the text".

If the passage has no clinical substance (an index, a table of contents, references, a figure caption, a page header), reply with exactly: SKIP

PASSAGE:
{passage}

Question:"""


def _key(text: str) -> str:
    """Identity of a passage. Same rule the retriever dedupes by."""
    return text[:120]


def _looks_like_prose(text: str) -> bool:
    """Skip index pages and OCR debris before spending a model call on them."""
    if len(text) < 500 or "indd" in text:
        return False
    letters = sum(ch.isalpha() for ch in text)
    return letters / len(text) > 0.65


QUESTIONS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "retrieval_questions.json"
)


def sample_passages(n_per_book: int, source: str) -> list[dict[str, Any]]:
    client = get_client()
    out: list[dict[str, Any]] = []
    for book, flt in (
        # DiPiro predates the `book` tag, so it is "everything not RxPrep".
        ("dipiro", models.Filter(must_not=[RXPREP_CONDITION])),
        ("rxprep", RXPREP_FILTER),
    ):
        points = client.query_points(
            source,
            query=models.SampleQuery(sample=models.Sample.RANDOM),
            query_filter=flt,
            limit=n_per_book * 4,
            with_payload=True,
        ).points
        kept = 0
        for p in points:
            payload = p.payload or {}
            text = str(payload.get("page_content", ""))
            if not _looks_like_prose(text):
                continue
            meta = payload.get("metadata", {}) or {}
            out.append({"book": book, "page": meta.get("page"), "text": text})
            kept += 1
            if kept == n_per_book:
                break
    return out


def build_questions(n: int, source: str) -> list[dict[str, Any]]:
    """Sample passages and write the question each answers — once.

    Saved to retrieval_questions.json and reused, so two collections (or
    two retrieval designs) are compared on exactly the same questions.
    Passages are sampled from the collection given, which should be the
    smaller one: every passage of the hybrid collection also exists in the
    dense one, not the other way round.
    """
    out: list[dict[str, Any]] = []
    passages = sample_passages(n // 2, source)
    for i, item in enumerate(passages, start=1):
        question = invoke_role(
            Role.NAVIGATOR, QUESTION_PROMPT.format(passage=item["text"][:2500])
        ).strip()
        if not question or question.upper().startswith("SKIP"):
            print(f"  [{i}/{len(passages)}] skipped (no clinical substance)")
            continue
        out.append(
            {
                "book": item["book"],
                "page": item["page"],
                "question": re.sub(r"\s+", " ", question),
                "source_key": _key(item["text"]),
            }
        )
        print(f"  [{i}/{len(passages)}] {item['book']:<6} {out[-1]['question'][:90]}")
    with open(QUESTIONS_FILE, "w") as fh:
        json.dump(out, fh, indent=2)
    return out


def run(questions: list[dict[str, Any]]) -> dict[str, Any]:
    retriever: BalancedRetriever = get_balanced_retriever()
    rows: list[dict[str, Any]] = []

    for i, item in enumerate(questions, start=1):
        question = item["question"]
        source = item["source_key"]

        glob = retriever.vs.similarity_search(question, k=retriever.k_global)
        rx = retriever.vs.similarity_search(question, k=retriever.k_rxprep, filter=RXPREP_FILTER)
        dense_hit = any(_key(d.page_content) == source for d in glob)
        candidate_hit = dense_hit or any(_key(d.page_content) == source for d in rx)

        kept = retriever.invoke(question)
        rank = next(
            (r for r, d in enumerate(kept, start=1) if _key(d.page_content) == source), None
        )
        rows.append(
            {
                "book": item["book"],
                "page": item["page"],
                "question": question,
                "dense_hit": dense_hit,
                "candidate_hit": candidate_hit,
                "rank_after_rerank": rank,
                "kept": len(kept),
                "kept_scores": [
                    round(float(d.metadata.get("relevance_score", 0)), 3) for d in kept
                ],
            }
        )
        print(
            f"  [{i}/{len(questions)}] {item['book']:<6} p.{item['page']!s:<5} "
            f"dense {'Y' if dense_hit else '-'} cand {'Y' if candidate_hit else '-'} "
            f"rank {rank or '-'}  {question[:80]}"
        )
        time.sleep(6.5)  # Cohere trial keys allow 10 rerank calls a minute

    return {"rows": rows, "k_global": retriever.k_global, "k_rxprep": retriever.k_rxprep}


def summarise(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    def block(sub: list[dict[str, Any]]) -> dict[str, str]:
        n = len(sub)
        if not n:
            return {}
        hit = sum(r["rank_after_rerank"] is not None for r in sub)
        mrr = sum(1 / r["rank_after_rerank"] for r in sub if r["rank_after_rerank"]) / n
        return {
            "questions": str(n),
            "first-stage recall": f"{sum(r['dense_hit'] for r in sub) / n:.0%}",
            "candidate recall": f"{sum(r['candidate_hit'] for r in sub) / n:.0%}",
            "hit rate (reaches generator)": f"{hit / n:.0%}",
            "MRR": f"{mrr:.2f}",
        }

    out = {"all": block(rows)}
    for book in ("dipiro", "rxprep"):
        out[book] = block([r for r in rows if r["book"] == book])
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=40, help="passages to sample (split per book)")
    parser.add_argument(
        "--new-questions",
        metavar="COLLECTION",
        help="sample fresh passages from COLLECTION and rewrite the question set",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    if args.new_questions or not os.path.exists(QUESTIONS_FILE):
        print(f"Writing {args.n} questions from {args.new_questions or collection_name()}")
        questions = build_questions(args.n, args.new_questions or collection_name())
    else:
        with open(QUESTIONS_FILE) as fh:
            questions = json.load(fh)
    print(f"Scoring {len(questions)} questions against {collection_name()}")

    started = datetime.now(UTC)
    result = run(questions)
    summary = summarise(result["rows"])

    print("\nRETRIEVAL SUMMARY")
    for scope, metrics in summary.items():
        print(f"  {scope}: " + " · ".join(f"{k} {v}" for k, v in metrics.items()))

    out = {
        "run_at": started.isoformat(timespec="seconds"),
        "collection": collection_name(),
        "reranker": rerank_model(),
        "summary": summary,
        **result,
    }
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), f"retrieval_results_{collection_name()}.json"
    )
    with open(path, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nSaved to {path}")


if __name__ == "__main__":
    main()
