"""
RAGAS scores for ARIA's answers, judged by Qwen on Groq.

Runs in its own environment: RAGAS 0.4 imports a LangChain module that the
app's LangChain 1.x no longer ships, so it cannot share `aria_env`.

    python3 -m venv ragas_env
    ragas_env/bin/pip install -r evals/requirements-ragas.txt
    ragas_env/bin/python evals/ragas_eval.py --label after

Reads evals/ragas/answers_<label>.json (from build_ragas_dataset.py) and
writes evals/ragas/scores_<label>.json, saving after every question so a run
that hits the provider's daily quota resumes where it stopped.

Metrics, all reference-free (ARIA has no expert-written gold answers):

  faithfulness       share of the answer's claims the passages support
  answer_relevancy   how well the answer addresses the question
  context_precision  were the passages that the answer needed ranked first
  context_relevance  how relevant the retrieved passages are to the question

One deviation from stock RAGAS, forced by the provider: Groq caps qwen at
1,000 output tokens a minute, and faithfulness asks the judge to restate a
long answer as a list of claims and then rule on each — well over 1,000
tokens for a full ARIA answer, so the call is cut off and scores NaN. The
answer is therefore scored in sections of at most ~1,100 characters, split
on paragraph boundaries, and the answer's faithfulness is the length-
weighted mean of its sections. The judge sees the same passages throughout.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import warnings
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from langchain_core.callbacks import get_usage_metadata_callback
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from ragas import EvaluationDataset, RunConfig, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    ContextRelevance,
    Faithfulness,
    LLMContextPrecisionWithoutReference,
    ResponseRelevancy,
)

DATA = Path(__file__).parent / "ragas"
JUDGE_MODEL = "qwen/qwen3.8-27b"
SECTION_CHARS = 1100
MARKERS = re.compile(r"\s*\[\[\d+(?:\s*,\s*\d+)*\]\]")

METRICS = {
    "faithfulness": Faithfulness,
    "answer_relevancy": lambda: ResponseRelevancy(strictness=1),  # Groq allows n=1 only
    "context_precision": LLMContextPrecisionWithoutReference,
    "context_relevance": ContextRelevance,
}
# Column RAGAS writes for each metric.
COLUMN = {
    "faithfulness": "faithfulness",
    "answer_relevancy": "answer_relevancy",
    "context_precision": "llm_context_precision_without_reference",
    "context_relevance": "nv_context_relevance",
}


def sections(answer: str, limit: int = SECTION_CHARS) -> list[str]:
    """Split on blank lines into chunks of at most ~`limit` characters."""
    out: list[str] = []
    current = ""
    for block in re.split(r"\n\s*\n", answer):
        block = block.strip()
        if not block:
            continue
        if current and len(current) + len(block) + 2 > limit:
            out.append(current)
            current = block
        else:
            current = f"{current}\n\n{block}" if current else block
    if current:
        out.append(current)
    return out


def score(samples: list[dict[str, Any]], metric: str, llm: Any, emb: Any) -> list[float]:
    result = evaluate(
        EvaluationDataset.from_list(samples),
        metrics=[METRICS[metric]()],
        llm=llm,
        embeddings=emb,
        run_config=RunConfig(max_workers=1, max_retries=12, max_wait=120, timeout=900),
        show_progress=False,
        raise_exceptions=False,
    )
    return [float(v) for v in result.to_pandas()[COLUMN[metric]]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--metrics", default=",".join(METRICS))
    parser.add_argument("--limit", type=int, help="score only the first N questions")
    args = parser.parse_args()
    wanted = args.metrics.split(",")

    rows = json.loads((DATA / f"answers_{args.label}.json").read_text())[: args.limit]
    out_path = DATA / f"scores_{args.label}.json"
    scores: dict[str, dict[str, Any]] = (
        json.loads(out_path.read_text()) if out_path.exists() else {}
    )

    llm = LangchainLLMWrapper(
        ChatGroq(
            model=JUDGE_MODEL,
            temperature=0,
            max_tokens=1000,  # Groq's per-minute output cap for this model
            max_retries=10,
            reasoning_effort="none",
        )
    )
    emb = LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2"))

    for row in rows:
        q = row["question"]
        entry = scores.setdefault(q, {})
        answer = MARKERS.sub("", row["answer"])
        for metric in wanted:
            if metric in entry and not math.isnan(entry[metric]):
                continue
            with get_usage_metadata_callback() as usage:
                if metric == "faithfulness":
                    parts = sections(answer)
                    vals = score(
                        [
                            {"user_input": q, "response": p, "retrieved_contexts": row["contexts"]}
                            for p in parts
                        ],
                        metric,
                        llm,
                        emb,
                    )
                    ok = [
                        (v, len(p)) for v, p in zip(vals, parts, strict=True) if not math.isnan(v)
                    ]
                    value = (
                        sum(v * n for v, n in ok) / sum(n for _, n in ok) if ok else float("nan")
                    )
                    entry["faithfulness_sections"] = f"{len(ok)}/{len(parts)}"
                else:
                    sample = {
                        "user_input": q,
                        "response": answer,
                        "retrieved_contexts": row["contexts"],
                    }
                    value = score([sample], metric, llm, emb)[0]
            tokens = sum(u.get("total_tokens", 0) for u in usage.usage_metadata.values())
            entry[metric] = value
            entry[f"{metric}_tokens"] = tokens
            out_path.write_text(json.dumps(scores, indent=2))
            print(f"  {metric:<18} {value:.3f}  ({tokens} tokens)  {q[:60]}", flush=True)

    print(f"\n{args.label}: means over {len(rows)} questions")
    for metric in wanted:
        vals = [scores[r["question"]].get(metric, float("nan")) for r in rows]
        good = [v for v in vals if not math.isnan(v)]
        mean = sum(good) / len(good) if good else float("nan")
        spent = sum(scores[r["question"]].get(f"{metric}_tokens", 0) for r in rows)
        print(f"  {metric:<18} {mean:.3f}  (n={len(good)}, {spent} judge tokens)")


if __name__ == "__main__":
    main()
