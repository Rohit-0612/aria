"""
Drug-name retrieval eval — does retrieval find the drug the question names?

The synthetic retrieval eval writes each question from its source passage,
so the question shares the passage's vocabulary and dense search finds it
easily: on that set, dense-only and hybrid search scored the same. The case
hybrid search exists for is different — a real question naming a specific
drug, where dense embeddings blur neighbouring names ("Can sitagliptin be
used in renal impairment?" retrieved a bivalirudin passage).

This measures that case directly and without an LLM judge: for questions
that each name one drug, how often does a passage that reaches the
generator actually mention that drug?

    ARIA_QDRANT_COLLECTION=aria_medical    aria_env/bin/python evals/drug_name_eval.py
    ARIA_QDRANT_COLLECTION=aria_medical_v2 aria_env/bin/python evals/drug_name_eval.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.config import rerank_model
from llm.errors import AriaRetrievalError
from retrieval.reranker import get_balanced_retriever
from vectorstore.qdrant_store import collection_name

# (drug, question). Mostly newer or less common agents whose names have
# close neighbours — the names dense embeddings are likeliest to blur.
CASES = [
    ("sitagliptin", "Can sitagliptin be used in renal impairment?"),
    ("linagliptin", "Does linagliptin need a dose adjustment in kidney disease?"),
    ("empagliflozin", "What are the adverse effects of empagliflozin?"),
    ("dapagliflozin", "Is dapagliflozin used in heart failure?"),
    ("semaglutide", "How is semaglutide dosed?"),
    ("finerenone", "What is finerenone used for in diabetic kidney disease?"),
    ("sacubitril", "When is sacubitril/valsartan preferred over an ACE inhibitor?"),
    ("ivabradine", "What is the role of ivabradine in heart failure?"),
    ("idarucizumab", "When is idarucizumab given?"),
    ("andexanet", "What does andexanet alfa reverse?"),
    ("apixaban", "How is apixaban dosed in atrial fibrillation?"),
    ("ticagrelor", "What are the side effects of ticagrelor?"),
    ("prasugrel", "Who should not receive prasugrel?"),
    ("ezetimibe", "How does ezetimibe lower LDL cholesterol?"),
    ("febuxostat", "What is the cardiovascular warning for febuxostat?"),
    ("tolvaptan", "What monitoring is needed with tolvaptan?"),
    ("dolutegravir", "What are the interactions of dolutegravir with antacids?"),
    ("bedaquiline", "What are the QT effects of bedaquiline?"),
    ("varenicline", "How is varenicline used for smoking cessation?"),
    ("lacosamide", "What is lacosamide used for?"),
]


def mentions(drug: str, docs: list[Any]) -> int:
    return sum(1 for d in docs if drug in d.page_content.lower())


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    retriever = get_balanced_retriever()
    rows: list[dict[str, Any]] = []
    for drug, question in CASES:
        candidates = retriever.vs.similarity_search(question, k=retriever.k_global)
        try:
            kept = retriever.invoke(question)
        except AriaRetrievalError:
            # Nothing cleared the relevance floor: the consultation would
            # fail. Counted as finding nothing, which is what it is.
            kept = []
        row: dict[str, Any] = {
            "drug": drug,
            "question": question,
            "candidates_naming_it": mentions(drug, candidates),
            "kept_naming_it": mentions(drug, kept),
            "kept": len(kept),
        }
        rows.append(row)
        print(
            f"  {drug:<14} candidates {row['candidates_naming_it']:>2}/{len(candidates):<2}"
            f"  reaches generator {row['kept_naming_it']}/{row['kept']}"
        )
        time.sleep(6.5)  # Cohere trial: 10 rerank calls a minute

    n = len(rows)
    found = sum(r["kept_naming_it"] > 0 for r in rows)
    density = sum(r["kept_naming_it"] for r in rows) / max(1, sum(r["kept"] for r in rows))
    summary = {
        "collection": collection_name(),
        "reranker": rerank_model(),
        "questions": n,
        "retrieval failed outright": sum(r["kept"] == 0 for r in rows),
        "answerable (a kept passage names the drug)": f"{found}/{n}",
        "kept passages naming the drug": f"{density:.0%}",
    }
    print("\n" + json.dumps(summary, indent=2))
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), f"drug_name_results_{collection_name()}.json"
    )
    with open(path, "w") as fh:
        json.dump({"summary": summary, "rows": rows}, fh, indent=2)


if __name__ == "__main__":
    main()
