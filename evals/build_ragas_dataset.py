"""
Build the dataset `ragas_eval.py` scores: question, answer, retrieved passages.

Runs in the app's own environment. RAGAS pins an older LangChain than the
app does, so generating and scoring are separate steps in separate envs.

It runs retrieval and the production generator only. The guardrail, query
rewrite and Judge are skipped: RAGAS needs none of them, and they spend the
small model's daily quota, which the live app shares. Retrieval therefore
uses the question as asked rather than the rewritten search query.

`--prompt-ref` builds the answers with the generator prompt as it was at a
git revision, so a prompt change can be measured before and after on the
same questions and the same passages.

    aria_env/bin/python evals/build_ragas_dataset.py --label after
    aria_env/bin/python evals/build_ragas_dataset.py --label before --prompt-ref HEAD~1
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.navigator_agent import _get_retriever
from evals.cases import ANSWER_QUESTIONS
from llm import generator
from llm.config import Role
from llm.llm_setup import stream_role
from llm.prompts import ANSWER_PROMPT

OUT_DIR = Path(__file__).parent / "ragas"


def prompt_at(ref: str) -> str:
    """ANSWER_PROMPT as committed at `ref`."""
    source = subprocess.run(
        ["git", "show", f"{ref}:llm/prompts.py"], capture_output=True, text=True, check=True
    ).stdout
    namespace: dict[str, Any] = {}
    exec(compile(source, f"{ref}:llm/prompts.py", "exec"), namespace)
    prompt: str = namespace["ANSWER_PROMPT"]
    return prompt


def answer_with(prompt: str, question: str, chunks: list[Any]) -> str:
    filled = prompt.format(context=generator.format_passages(chunks), question=question)
    return "".join(stream_role(Role.GENERATOR, filled))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, help="dataset name, e.g. before / after")
    parser.add_argument("--prompt-ref", help="git revision whose generator prompt to use")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    prompt = prompt_at(args.prompt_ref) if args.prompt_ref else ANSWER_PROMPT
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"answers_{args.label}.json"
    rows: list[dict[str, Any]] = json.loads(out.read_text()) if out.exists() else []
    done = {r["question"] for r in rows}

    for i, question in enumerate(ANSWER_QUESTIONS, start=1):
        if question in done:
            continue
        t0 = time.time()
        chunks = _get_retriever().invoke(question)
        answer = answer_with(prompt, question, chunks)
        rows.append(
            {
                "question": question,
                "answer": answer,
                "contexts": [c.page_content for c in chunks],
                "prompt_ref": args.prompt_ref or "working tree",
            }
        )
        out.write_text(json.dumps(rows, indent=2))  # saved after every answer
        print(f"[{i}] {time.time() - t0:.1f}s · {len(answer)} chars", flush=True)
        time.sleep(5)
    print(f"{len(rows)} answers in {out}")


if __name__ == "__main__":
    main()
