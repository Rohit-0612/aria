"""
Teaching-coverage eval: does an answer teach the topic, not just stay true?

Two steps, deliberately separate so each spends only one provider's quota:

  generate  runs the real pipeline over `evals/coverage_cases.py` and saves
            every answer (Groq). Paced for Groq's per-minute budget, and it
            stops at the first *daily* limit instead of retrying into it —
            the live demo shares the same key.
  grade     scores the saved answers with Gemini (a different model family
            from both the app's generator and its Judge) and never calls
            Groq. Per facet: covered / partial / missing; plus 1-5 on
            structure, explaining *why*, and defining terms.

Coverage = (covered + 0.5 x partial) / facets. Groundedness is not graded
here — the main eval (`run_evals.py`) and the app's Judge already do that,
and the two must be read together: a long answer can cover everything by
inventing it.

Run from the project root:
    aria_env/bin/python evals/coverage_eval.py generate --label baseline
    aria_env/bin/python evals/coverage_eval.py grade    --label baseline
    aria_env/bin/python evals/coverage_eval.py report   baseline [other ...]

    --grader qwen/qwen3.8-27b  grades (and reports) on Groq instead, into
                               grades_<label>@qwen3.8-27b.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from typing import Any

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from evals.coverage_cases import COVERAGE_CASES

load_dotenv()

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "coverage")
MARKER = re.compile(r"\[\[(\d+)\]\]")
# Groq reserves prompt + max_tokens of an 8,000-token minute per call; with a
# teaching answer the Judge alone takes most of it, so consultations are kept
# well over a minute apart.
PACING_S = 40
DEFAULT_GRADER_MODEL = (
    "gemini-3.5-flash"  # kept out of the generator cascade so grading has its own quota
)


def _path(kind: str, label: str, grader: str | None = None) -> str:
    """grades from a non-default grader are kept in their own file, so two
    graders' scores are never averaged together by accident."""
    suffix = "" if not grader or grader == DEFAULT_GRADER_MODEL else "@" + grader.split("/")[-1]
    return os.path.join(OUT_DIR, f"{kind}_{label}{suffix}.json")


def load_answers(label: str) -> dict[str, Any]:
    """The saved answers, with each passage's text joined back in when the
    local passages file is present (it is not committed — see save_answers)."""
    with open(_path("answers", label)) as f:
        data: dict[str, Any] = json.load(f)
    texts_path = _path("passages", label)
    if os.path.exists(texts_path):
        with open(texts_path) as f:
            texts: dict[str, list[str]] = json.load(f)
        for cid, row in data.get("rows", {}).items():
            for p, t in zip(row.get("passages", []), texts.get(cid, []), strict=False):
                p["text"] = t
    return data


def save_answers(label: str, data: dict[str, Any]) -> None:
    """Answers and passage references go in `answers_<label>.json`; the
    passages' text — copyrighted textbook pages — in `passages_<label>.json`,
    which .gitignore keeps out of the repository. The model-free citation
    check needs the text, so it runs where the passages file exists."""
    texts: dict[str, list[str]] = {}
    rows: dict[str, Any] = {}
    for cid, row in data.get("rows", {}).items():
        row = dict(row)
        if "passages" in row:
            texts[cid] = [p.get("text", "") for p in row["passages"]]
            row["passages"] = [{k: v for k, v in p.items() if k != "text"} for p in row["passages"]]
        rows[cid] = row
    with open(_path("answers", label), "w") as f:
        json.dump({**data, "rows": rows}, f, indent=1)
    if any(any(t) for t in texts.values()):
        with open(_path("passages", label), "w") as f:
            json.dump(texts, f)


def _is_daily_limit(text: str) -> bool:
    t = text.lower()
    return "per day" in t or "tpd" in t or "rpd" in t or "daily" in t


# ── generate (Groq) ────────────────────────────────────────────────────


def generate(label: str, only: list[str] | None) -> None:
    from evals.run_evals import consult  # imports the graph; Groq from here on

    cases = [c for c in COVERAGE_CASES if not only or c["id"] in only]
    os.makedirs(OUT_DIR, exist_ok=True)
    path = _path("answers", label)
    saved: dict[str, Any] = load_answers(label) if os.path.exists(path) else {}
    rows: dict[str, Any] = saved.get("rows", {})

    for i, case in enumerate(cases, start=1):
        if case["id"] in rows and "error" not in rows[case["id"]]:
            print(f"  [{i}/{len(cases)}] {case['id']}: already generated, skipping")
            continue
        print(f"  [{i}/{len(cases)}] {case['id']}")
        state, latency = consult(case["question"])
        failure = state["failure"]
        if failure is not None:
            message = f"{failure['code']} {failure['message']}"
            rows[case["id"]] = {"error": message}
            print(f"    FAILED: {message}")
            if _is_daily_limit(message):
                print("    daily limit reached — stopping so the live demo keeps its quota")
                break
        else:
            chunks = state["chunks"]
            answer = state["answer"]
            rows[case["id"]] = {
                "question": case["question"],
                "answer": answer,
                "latency_s": round(latency, 1),
                "n_passages": len(chunks),
                "passages": [
                    {
                        "book": c.metadata.get("book", "dipiro"),
                        "page": c.metadata.get("page_label") or c.metadata.get("page"),
                        "chars": len(c.page_content),
                        "text": c.page_content,
                    }
                    for c in chunks
                ],
                "markers": len(MARKER.findall(answer)),
                "words": len(answer.split()),
                "app_confidence": state["confidence"],
                "model": state.get("generator_model"),
                "outline": state.get("outline") or [],
            }
            print(
                f"    {latency:.1f}s · {len(chunks)} passages · "
                f"{rows[case['id']]['words']} words · judge {state['confidence']}"
            )
        save_answers(
            label,
            {
                **saved,
                "label": label,
                "generated_at": datetime.now(UTC).isoformat(),
                "rows": rows,
            },
        )
        if i < len(cases):
            time.sleep(PACING_S)
    print(f"\nsaved {path}")


# ── grade (Gemini) ─────────────────────────────────────────────────────

GRADE_PROMPT = """You are grading a pharmacotherapy answer written for a pharmacy student.
Judge one thing: does it TEACH the topic — would a student who reads only this answer understand it?
Do not grade style for its own sake, and do not reward length.

QUESTION:
{question}

FACETS a complete teaching answer covers:
{facets}

ANSWER (inline markers like [[3]] are citations to sources you cannot see; ignore them):
{answer}

For each facet decide:
- "covered": the idea is explained correctly and clearly enough for a student to understand it
- "partial": mentioned, but too vague, unexplained, or incomplete to learn from
- "missing": absent, or stated incorrectly (say so in the note)

Then score 1-5:
- structure: is it organised so a learner can follow it (a clear bottom line, logical sections, comparison where useful)?
- explains_why: does it explain mechanisms and reasons, not only list conclusions?
- defines_terms: are technical terms and abbreviations explained when first used?

Respond ONLY with JSON:
{{"facets": [{{"i": <facet number>, "verdict": "covered|partial|missing", "note": "<short>"}}],
  "structure": <1-5>, "explains_why": <1-5>, "defines_terms": <1-5>,
  "biggest_gap": "<one sentence: the most important thing a student would still not understand>"}}"""


def _gemini_key() -> str:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY is not set (add it to .env)")
    return key


def gemini_json(prompt: str, model: str) -> dict[str, Any]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    for attempt in range(1, 6):
        r = httpx.post(url, headers={"x-goog-api-key": _gemini_key()}, json=body, timeout=120)
        if r.status_code == 429 or r.status_code >= 500:
            wait = 15 * attempt
            print(f"    grader {r.status_code} — waiting {wait}s")
            time.sleep(wait)
            continue
        r.raise_for_status()
        data = r.json()
        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match is None:
            raise ValueError(f"grader returned no JSON: {text[:200]!r}")
        parsed: dict[str, Any] = json.loads(match.group(0))
        return parsed
    raise RuntimeError("grader kept failing (rate limit or server error)")


def groq_json(prompt: str, model: str) -> dict[str, Any]:
    """The same rubric on a Groq model — for a grader from neither the
    Gemini family (which writes the teaching answers) nor gpt-oss (which
    wrote the baseline). `gemini-3.5-flash` turned out to be served by
    gemini-3.6-flash, the generator itself."""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        sys.exit("GROQ_API_KEY is not set")
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 3000,
        "response_format": {"type": "json_object"},
        "reasoning_format": "hidden",
    }
    for attempt in range(1, 6):
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json=body,
            timeout=120,
        )
        if r.status_code == 429 or r.status_code >= 500:
            if _is_daily_limit(r.text):
                raise RuntimeError(f"daily limit on {model}")
            wait = 20 * attempt
            print(f"    grader {r.status_code} — waiting {wait}s")
            time.sleep(wait)
            continue
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"] or ""
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match is None:
            raise ValueError(f"grader returned no JSON: {text[:200]!r}")
        parsed: dict[str, Any] = json.loads(match.group(0))
        return parsed
    raise RuntimeError("grader kept failing (rate limit or server error)")


def grade(label: str, grader: str | None = None) -> None:
    model: str = grader or os.getenv("ARIA_COVERAGE_GRADER_MODEL") or DEFAULT_GRADER_MODEL
    ask = gemini_json if model.startswith("gemini") else groq_json
    pause = 4 if ask is gemini_json else 30  # Groq: 8,000 tokens a minute
    answers = load_answers(label)["rows"]
    by_id = {c["id"]: c for c in COVERAGE_CASES}
    path = _path("grades", label, model)
    graded: dict[str, Any] = {}
    if os.path.exists(path):
        with open(path) as f:
            graded = json.load(f).get("rows", {})

    def save() -> None:
        with open(path, "w") as f:
            json.dump(
                {
                    "label": label,
                    "grader": model,
                    "graded_at": datetime.now(UTC).isoformat(),
                    "rows": graded,
                },
                f,
                indent=1,
            )

    for cid, row in answers.items():
        if cid in graded and "coverage" in graded[cid]:
            continue
        if "error" in row:
            graded[cid] = {"error": row["error"]}
            continue
        case = by_id[cid]
        facets = "\n".join(f"{i}. {f}" for i, f in enumerate(case["facets"], start=1))
        try:
            v = ask(
                GRADE_PROMPT.format(question=case["question"], facets=facets, answer=row["answer"]),
                model,
            )
        except (RuntimeError, ValueError) as exc:
            print(f"  stopping: {exc} — graded so far are saved; rerun later to finish")
            break
        verdicts = {int(x["i"]): x for x in v.get("facets", []) if isinstance(x, dict) and "i" in x}
        score = sum(
            1.0
            if verdicts.get(i, {}).get("verdict") == "covered"
            else 0.5
            if verdicts.get(i, {}).get("verdict") == "partial"
            else 0.0
            for i in range(1, len(case["facets"]) + 1)
        )
        graded[cid] = {
            "coverage": round(score / len(case["facets"]), 3),
            "structure": v.get("structure"),
            "explains_why": v.get("explains_why"),
            "defines_terms": v.get("defines_terms"),
            "biggest_gap": v.get("biggest_gap", ""),
            "facets": [
                {"facet": f, **{k: verdicts.get(i, {}).get(k) for k in ("verdict", "note")}}
                for i, f in enumerate(case["facets"], start=1)
            ],
        }
        print(
            f"  {cid:32s} coverage {graded[cid]['coverage']:.2f} · why {v.get('explains_why')} · terms {v.get('defines_terms')}"
        )
        save()
        time.sleep(pause)
    save()
    print(f"\nsaved {path}")


# ── citation check (no model) ──────────────────────────────────────────

# A number standing on its own: "2.5 mg", "<40%", "10 months" — not the
# digits inside a name such as SGLT2, CYP2C9, T1DM or "type-1".
_NUMBER = re.compile(r"(?<![A-Za-z\d.])(?<![A-Za-z]-)\d+(?:[.,]\d+)?(?![A-Za-z\d])")
_UNIT_SPLIT = re.compile(r"\n+|(?<=[.!?])\s+(?=[A-Z*])")


def number_support(answer: str, passages: list[dict[str, Any]]) -> tuple[int, int]:
    """(numbers found in their cited passages, numbers in cited statements).

    The cheapest honest grounding check there is: a dose, threshold or
    percentage attached to [[n]] must be written in passage n. It needs no
    model, so it cannot be argued with — and it catches the failure that
    matters most, a specific number from the model's memory dressed in a
    citation.
    """
    texts = [p.get("text", "") for p in passages]
    found = total = 0
    for unit in _UNIT_SPLIT.split(answer):
        cited = [int(m) for m in MARKER.findall(unit)]
        if not cited or unit.lstrip().startswith(">"):
            continue
        body = MARKER.sub(" ", unit)
        body = re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", body)  # list numbering is not a claim
        sources = " ".join(texts[n - 1] for n in cited if 1 <= n <= len(texts)).replace(",", "")
        for num in _NUMBER.findall(body):
            total += 1
            plain = re.escape(num.replace(",", ""))
            if re.search(rf"(?<![\d.]){plain}(?![\d]|\.\d)", sources):
                found += 1
    return found, total


# ── report ─────────────────────────────────────────────────────────────


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def report(labels: list[str], grader: str | None = None) -> None:
    print(f"{'':22s}" + "".join(f"{label:>14s}" for label in labels))
    cols: list[dict[str, float]] = []
    for label in labels:
        answers = load_answers(label)["rows"]
        with open(_path("grades", label, grader)) as f:
            grades = json.load(f)["rows"]
        ok = [cid for cid, g in grades.items() if "error" not in g]
        a = [answers[c] for c in ok]
        g = [grades[c] for c in ok]
        cols.append(
            {
                "answered": len(ok),
                "coverage": _mean([x["coverage"] for x in g]),
                "explains why (1-5)": _mean([x["explains_why"] for x in g]),
                "defines terms (1-5)": _mean([x["defines_terms"] for x in g]),
                "structure (1-5)": _mean([x["structure"] for x in g]),
                "app judge": _mean(
                    [x["app_confidence"] for x in a if x["app_confidence"] is not None]
                ),
                "passages": _mean([x["n_passages"] for x in a]),
                "words": _mean([x["words"] for x in a]),
                "latency s (mean)": _mean([x["latency_s"] for x in a]),
            }
        )
        nums = [
            number_support(x["answer"], x["passages"])
            for x in a
            if any("text" in p for p in x["passages"])
        ]
        found, total = sum(n[0] for n in nums), sum(n[1] for n in nums)
        cols[-1]["cited numbers in source"] = found / total if total else float("nan")
    for key in cols[0]:
        print(f"{key:22s}" + "".join(f"{c[key]:>14.2f}" for c in cols))


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--label", required=True)
    g.add_argument("--only", nargs="*", help="case ids to run (default: all)")
    gr = sub.add_parser("grade")
    gr.add_argument("--label", required=True)
    gr.add_argument("--grader", help="grader model (default: Gemini); a Groq id grades on Groq")
    r = sub.add_parser("report")
    r.add_argument("labels", nargs="+")
    r.add_argument("--grader", help="read the grades this grader wrote")
    args = p.parse_args()
    if args.cmd == "generate":
        generate(args.label, args.only)
    elif args.cmd == "grade":
        grade(args.label, args.grader)
    else:
        report(args.labels, args.grader)


if __name__ == "__main__":
    main()
