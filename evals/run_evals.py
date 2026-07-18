"""
ARIA evaluation harness.

Runs the real pipeline components over a small labelled set and reports:
  1. Guardrail accuracy   — in-scope vs out-of-scope classification
  2. Retrieval health     — chunks returned, source balance across books
  3. Answer quality       — groundedness & relevance (0-1), scored by an
                            independent LLM judge that sees the retrieved
                            context (separate prompt from the app's Judge)

Run from the project root:
    aria_env/bin/python evals/run_evals.py
Results are printed and saved to evals/results.json.
"""

import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.guardrail_agent import check_guardrail
from agents.judge_agent import judge_answer
from agents.navigator_agent import navigator
from llm.generator import generate_answer
from llm.llm_setup import get_llm

IN_SCOPE = [
    "What is the first-line treatment for hypertension?",
    "How does metformin work and what are its main adverse effects?",
    "What antibiotics are used for community-acquired pneumonia?",
    "What monitoring is required for a patient on warfarin?",
    "How should statin therapy be selected for a diabetic patient?",
    "What are the treatment options for acute asthma exacerbation?",
]

OUT_OF_SCOPE = [
    "What is the price of Bitcoin today?",
    "Who won the last football World Cup?",
    "Write me a poem about the ocean.",
    "How do I fix a segmentation fault in C++?",
]

EVAL_JUDGE_PROMPT = """You are a strict, independent evaluator of a medical RAG system.

CONTEXT (retrieved textbook passages):
{context}

QUESTION: {question}

ANSWER: {answer}

Score the ANSWER on two axes, each 0.0-1.0:
- groundedness: every claim in the answer is supported by the CONTEXT (1.0 = fully supported, 0.0 = fabricated)
- relevance: the answer directly addresses the QUESTION (1.0 = fully, 0.0 = off-topic)

Respond ONLY with JSON: {{"groundedness": <float>, "relevance": <float>, "note": "<one short sentence>"}}"""


def eval_judge(question, answer, chunks):
    context = "\n\n".join(c.page_content for c in chunks)
    llm = get_llm(temperature=0)
    response = llm.invoke(
        EVAL_JUDGE_PROMPT.format(context=context, question=question, answer=answer)
    )
    match = re.search(r"\{.*\}", response.content, re.DOTALL)
    return json.loads(match.group(0))


def main():
    results = {"guardrail": [], "answers": []}

    # ── 1. Guardrail accuracy ────────────────────────────────────────
    print("=" * 60)
    print("1. GUARDRAIL")
    print("=" * 60)
    for query, expected in [(q, True) for q in IN_SCOPE] + [(q, False) for q in OUT_OF_SCOPE]:
        got = check_guardrail(query)
        results["guardrail"].append({"query": query, "expected": expected, "got": got})
        time.sleep(1)

    # ── 2 & 3. Retrieval + answer quality on in-scope queries ────────
    for i, query in enumerate(IN_SCOPE):
        print("\n" + "=" * 60)
        print(f"2. QUERY {i+1}/{len(IN_SCOPE)}: {query}")
        print("=" * 60)
        try:
            chunks = navigator(query)
            answer = generate_answer(query, chunks)
            scores = eval_judge(query, answer, chunks)
            app_confidence = judge_answer(query, answer, chunks)["confidence"]
            results["answers"].append({
                "query": query,
                "n_chunks": len(chunks),
                "n_rxprep": sum(1 for c in chunks if c.metadata.get("book") == "rxprep"),
                "groundedness": float(scores["groundedness"]),
                "relevance": float(scores["relevance"]),
                "app_confidence": float(app_confidence),
                "note": scores.get("note", ""),
            })
        except Exception as e:
            results["answers"].append({"query": query, "error": str(e)})
            print(f"FAILED: {e}")
        time.sleep(2)

    # ── Summary ──────────────────────────────────────────────────────
    g = results["guardrail"]
    correct = sum(1 for r in g if r["got"] == r["expected"])
    ok = [a for a in results["answers"] if "error" not in a]

    print("\n" + "=" * 60)
    print("EVAL SUMMARY")
    print("=" * 60)
    print(f"Guardrail accuracy : {correct}/{len(g)} ({correct/len(g):.0%})")
    for r in g:
        if r["got"] != r["expected"]:
            print(f"  MISCLASSIFIED: {r['query']!r} -> {r['got']}")
    if ok:
        mean = lambda k: sum(a[k] for a in ok) / len(ok)
        print(f"Answered           : {len(ok)}/{len(IN_SCOPE)} queries")
        print(f"Groundedness       : {mean('groundedness'):.2f} mean")
        print(f"Relevance          : {mean('relevance'):.2f} mean")
        print(f"App judge conf.    : {mean('app_confidence'):.2f} mean")
        print(f"Chunks per query   : {mean('n_chunks'):.1f} mean")
        print(f"Both books used    : {sum(1 for a in ok if 0 < a['n_rxprep'] < a['n_chunks'])}/{len(ok)} queries")
        passed = sum(1 for a in ok if a["groundedness"] >= 0.7 and a["relevance"] >= 0.7)
        print(f"Pass (both >= 0.7) : {passed}/{len(ok)}")
    failures = len(results["answers"]) - len(ok)
    if failures:
        print(f"Pipeline errors    : {failures}")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results saved to {out_path}")


if __name__ == "__main__":
    main()
