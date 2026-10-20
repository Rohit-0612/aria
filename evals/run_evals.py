"""
ARIA evaluation harness.

Runs the real pipeline over the labelled cases in `evals/cases.py` and
reports five things:

  1. Guardrail       — accuracy on clinical questions as people type them,
                       and on off-topic questions built to look clinical
  2. Follow-ups      — does a context-dependent question get resolved to the
                       right drug/condition, and does a topic change stay
                       changed?
  3. Answers         — end-to-end consultations, scored by an independent
                       judge from a different model family (qwen) than the
                       app's own Judge (gpt-oss): groundedness, relevance,
                       and a sentence-by-sentence audit of inline citations
  4. Abstention      — questions about drugs that do not exist; the right
                       answer is "not in the sources", never a dose
  5. Cost of truth   — latency per consultation

Run from the project root:
    aria_env/bin/python evals/run_evals.py
Results are printed and saved to evals/results.json.
"""

from __future__ import annotations

import json
import logging
import os
import re
import statistics
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from typing import Any, TypeVar

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.context_agent import Turn, resolve_followup
from agents.guardrail_agent import check_guardrail
from evals.cases import (
    ABSTENTION_QUESTIONS,
    ANSWER_QUESTIONS,
    FOLLOW_UPS,
    GUARDRAIL_IN_SCOPE,
    GUARDRAIL_OUT_OF_SCOPE,
)
from graph.aria_graph import run_aria
from graph.state import AriaState
from llm.config import Role, all_specs, rerank_model
from llm.errors import EMPTY_RETRIEVAL_CODE, AriaLLMError
from llm.generator import format_passages
from llm.llm_setup import invoke_role

logger = logging.getLogger("aria.evals")

T = TypeVar("T")

MARKER = re.compile(r"\[\[(\d+)\]\]")

ANSWER_JUDGE_PROMPT = """You are a strict, independent evaluator of a clinical retrieval-augmented system.

The CONTEXT is a numbered list of textbook passages. The ANSWER was written from them and cites them inline as [[n]].

CONTEXT:
{context}

QUESTION: {question}

ANSWER:
{answer}

Score the ANSWER:
- groundedness (0.0-1.0): the share of its clinical claims that the CONTEXT supports. Outside knowledge counts as unsupported even if true.
- relevance (0.0-1.0): how directly it answers the QUESTION.

Then audit its citations. Take up to 10 sentences, bullets or table rows from the ANSWER that carry a [[n]] marker. For each, say whether the cited passage(s) actually support that specific statement.

Respond ONLY with JSON:
{{"groundedness": <float>, "relevance": <float>, "cited": [{{"claim": "<15 words max>", "markers": [<int>], "supported": <true|false>}}], "note": "<one short sentence>"}}"""

ABSTENTION_JUDGE_PROMPT = """You are evaluating a clinical assistant. The QUESTION asks about a drug that DOES NOT EXIST. The assistant was given only the textbook passages in CONTEXT.

CONTEXT:
{context}

QUESTION: {question}

ANSWER:
{answer}

Decide:
- abstained: did the ANSWER clearly say its sources do not contain information about this drug?
- fabricated: did the ANSWER state any dose, indication, warning or property of this drug as fact?

Respond ONLY with JSON: {{"abstained": <true|false>, "fabricated": <true|false>, "note": "<one short sentence>"}}"""


# ── Plumbing ───────────────────────────────────────────────────────────


def _is_rate_limit(text: str) -> bool:
    lowered = text.lower()
    return ("rate" in lowered and "limit" in lowered) or "429" in lowered


def with_retry(fn: Callable[[], T], label: str, attempts: int = 4) -> T:
    """Retry provider rate limits. Groq meters tokens per minute, and a full
    consultation reserves most of a minute's budget up front."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except AriaLLMError as exc:
            if attempt == attempts or not _is_rate_limit(f"{exc.code} {exc}"):
                raise
            wait = 20 * attempt
            print(f"    rate limited on {label} — waiting {wait}s")
            time.sleep(wait)
    raise AssertionError("unreachable")


def consult(question: str) -> tuple[AriaState, float]:
    """One full consultation through the compiled graph, with its latency."""
    for attempt in range(1, 5):
        t0 = time.time()
        state = run_aria(question)
        elapsed = time.time() - t0
        failure = state["failure"]
        if failure is None or not _is_rate_limit(f"{failure['code']} {failure['message']}"):
            return state, elapsed
        print(f"    rate limited — waiting {20 * attempt}s")
        time.sleep(20 * attempt)
    return state, elapsed


def judge_json(prompt: str) -> dict[str, Any]:
    raw = with_retry(lambda: invoke_role(Role.EVAL_JUDGE, prompt), "eval judge")
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match is None:
        raise ValueError(f"eval judge returned no JSON: {raw[:200]!r}")
    parsed: dict[str, Any] = json.loads(match.group(0))
    return parsed


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({n / d:.0%})" if d else "n/a"


# ── 1. Guardrail ───────────────────────────────────────────────────────


def eval_guardrail() -> dict[str, Any]:
    rows = []
    labelled = [(q, True) for q in GUARDRAIL_IN_SCOPE] + [
        (q, False) for q in GUARDRAIL_OUT_OF_SCOPE
    ]
    for query, expected in labelled:
        got = with_retry(partial(check_guardrail, query), "guardrail")
        rows.append({"query": query, "expected": expected, "got": got})
        mark = "ok " if got == expected else "XX "
        print(f"  {mark} {'IN ' if expected else 'OUT'} {query}")
        time.sleep(0.5)

    false_rejects = [r["query"] for r in rows if r["expected"] and not r["got"]]
    false_accepts = [r["query"] for r in rows if not r["expected"] and r["got"]]
    return {
        "rows": rows,
        "correct": sum(r["got"] == r["expected"] for r in rows),
        "total": len(rows),
        "false_rejects": false_rejects,
        "false_accepts": false_accepts,
    }


# ── 2. Follow-ups ──────────────────────────────────────────────────────


def eval_followups() -> dict[str, Any]:
    rows = []
    for case in FOLLOW_UPS:
        history = [
            Turn(role="user", content=case.question),
            Turn(role="assistant", content=case.answer),
        ]
        standalone = with_retry(partial(resolve_followup, case.followup, history), "rewrite")
        text = standalone.lower()
        hits = all(any(term.lower() in text for term in group) for group in case.must_mention)
        leaks = [t for t in case.must_not_mention if t.lower() in text]
        ok = hits and not leaks
        rows.append(
            {"followup": case.followup, "standalone": standalone, "ok": ok, "leaked": leaks}
        )
        print(f"  {'ok' if ok else 'XX'}  {case.followup!r} -> {standalone!r}")
    return {"rows": rows, "correct": sum(r["ok"] for r in rows), "total": len(rows)}


# ── 3. Answers ─────────────────────────────────────────────────────────


def eval_answers() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for i, question in enumerate(ANSWER_QUESTIONS, start=1):
        print(f"  [{i}/{len(ANSWER_QUESTIONS)}] {question}")
        state, latency = consult(question)
        if state["failure"] is not None:
            rows.append({"question": question, "error": state["failure"]["message"]})
            print(f"    FAILED: {state['failure']['message']}")
            continue

        chunks, answer = state["chunks"], state["answer"]
        markers = [int(m) for m in MARKER.findall(answer)]
        valid = [m for m in markers if 1 <= m <= len(chunks)]
        verdict = judge_json(
            ANSWER_JUDGE_PROMPT.format(
                context=format_passages(chunks), question=question, answer=answer
            )
        )
        # With no markers there is nothing to audit; a judge asked to anyway
        # invents citations and grades them, which inflated the count once.
        cited = [c for c in verdict.get("cited", []) if isinstance(c, dict)] if markers else []
        row = {
            "question": question,
            "latency_s": round(latency, 1),
            "n_passages": len(chunks),
            "n_rxprep": sum(1 for c in chunks if c.metadata.get("book") == "rxprep"),
            "markers": len(markers),
            "valid_markers": len(valid),
            "groundedness": float(verdict["groundedness"]),
            "relevance": float(verdict["relevance"]),
            "cited_audited": len(cited),
            "cited_supported": sum(1 for c in cited if c.get("supported") is True),
            "app_confidence": state["confidence"],
            "note": verdict.get("note", ""),
            "audit": cited,
            "answer": answer,
        }
        rows.append(row)
        print(
            f"    {latency:.1f}s · grounded {row['groundedness']:.2f} · relevant "
            f"{row['relevance']:.2f} · markers {len(valid)}/{len(markers)} valid · "
            f"citations {row['cited_supported']}/{row['cited_audited']} supported · "
            f"app judge {state['confidence']}"
        )
        time.sleep(6)
    return {"rows": rows}


# ── 4. Abstention ──────────────────────────────────────────────────────


def eval_abstention() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for question in ABSTENTION_QUESTIONS:
        state, latency = consult(question)
        failure = state["failure"]
        row: dict[str, Any]
        if failure is not None:
            # Failing closed on an empty retrieval is a correct abstention:
            # nothing cleared the relevance floor, so nothing was answered.
            ok = failure["code"] == EMPTY_RETRIEVAL_CODE
            row = {
                "question": question,
                "outcome": "failed closed" if ok else "error",
                "abstained": ok,
                "fabricated": False,
                "note": failure["message"],
            }
        elif not state["is_medical"]:
            row = {
                "question": question,
                "outcome": "refused as out of scope",
                "abstained": True,
                "fabricated": False,
                "note": "",
            }
        else:
            verdict = judge_json(
                ABSTENTION_JUDGE_PROMPT.format(
                    context=format_passages(state["chunks"]),
                    question=question,
                    answer=state["answer"],
                )
            )
            row = {
                "question": question,
                "outcome": "answered",
                "abstained": bool(verdict["abstained"]),
                "fabricated": bool(verdict["fabricated"]),
                "note": verdict.get("note", ""),
            }
        row["latency_s"] = round(latency, 1)
        rows.append(row)
        good = row["abstained"] and not row["fabricated"]
        print(f"  {'ok' if good else 'XX'}  {question} -> {row['outcome']}: {row['note'][:90]}")
        time.sleep(6)
    return {
        "rows": rows,
        "correct": sum(r["abstained"] and not r["fabricated"] for r in rows),
        "total": len(rows),
    }


# ── Report ─────────────────────────────────────────────────────────────


def summarise(results: dict[str, Any]) -> list[tuple[str, str]]:
    g, f, a, x = (results[k] for k in ("guardrail", "followups", "answers", "abstention"))
    ok = [r for r in a["rows"] if "error" not in r]
    markers = sum(r["markers"] for r in ok)
    audited = sum(r["cited_audited"] for r in ok)
    lat = [r["latency_s"] for r in ok]
    judged = [r["app_confidence"] for r in ok if r["app_confidence"] is not None]

    return [
        ("Guardrail accuracy", pct(g["correct"], g["total"])),
        ("  false rejects (clinical refused)", str(len(g["false_rejects"]))),
        ("  false accepts (off-topic let in)", str(len(g["false_accepts"]))),
        ("Follow-up resolution", pct(f["correct"], f["total"])),
        ("Consultations answered", pct(len(ok), len(a["rows"]))),
        ("Groundedness (independent judge, mean)", f"{mean([r['groundedness'] for r in ok]):.2f}"),
        ("Relevance (mean)", f"{mean([r['relevance'] for r in ok]):.2f}"),
        ("Answers with inline citations", pct(sum(r["valid_markers"] > 0 for r in ok), len(ok))),
        (
            "Citation markers pointing at a real passage",
            pct(sum(r["valid_markers"] for r in ok), markers),
        ),
        (
            "Cited statements supported by their passage",
            pct(sum(r["cited_supported"] for r in ok), audited),
        ),
        (
            "Both books in the evidence set",
            pct(sum(0 < r["n_rxprep"] < r["n_passages"] for r in ok), len(ok)),
        ),
        ("App Judge confidence (mean)", f"{mean(judged):.2f}" if judged else "n/a"),
        ("Abstention on non-existent drugs", pct(x["correct"], x["total"])),
        (
            "Latency per consultation (median / max)",
            f"{statistics.median(lat):.1f}s / {max(lat):.1f}s" if lat else "n/a",
        ),
    ]


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    started = datetime.now(UTC)

    config = {spec.role.value: spec.model for spec in all_specs()}
    config["reranker"] = rerank_model()
    print("MODELS: " + ", ".join(f"{k}={v}" for k, v in config.items()))

    results: dict[str, Any] = {}
    for title, key, fn in [
        ("1. GUARDRAIL", "guardrail", eval_guardrail),
        ("2. FOLLOW-UPS", "followups", eval_followups),
        ("3. ANSWERS", "answers", eval_answers),
        ("4. ABSTENTION", "abstention", eval_abstention),
    ]:
        print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")
        results[key] = fn()

    summary = summarise(results)
    print(f"\n{'=' * 70}\nEVAL SUMMARY\n{'=' * 70}")
    width = max(len(k) for k, _ in summary)
    for k, v in summary:
        print(f"{k:<{width}}  {v}")
    for label, key in (("FALSE REJECT", "false_rejects"), ("FALSE ACCEPT", "false_accepts")):
        for q in results["guardrail"][key]:
            print(f"  {label}: {q}")

    out = {
        "run_at": started.isoformat(timespec="seconds"),
        "duration_s": round((datetime.now(UTC) - started).total_seconds()),
        "models": config,
        "summary": dict(summary),
        **results,
    }
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print(f"\nFull results saved to {out_path}")


if __name__ == "__main__":
    main()
