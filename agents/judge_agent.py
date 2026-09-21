"""
Judge agent — scores an answer for groundedness and relevance.

Two failure modes are kept strictly apart, because conflating them is how a
number that means nothing ends up rendered on a calibrated gauge:

  * the model replies but the JSON cannot be parsed -> the answer is real
    but *unadjudicated*. Confidence is None. It was previously 0.5, which
    the UI drew as a genuine "0.50 judge" score.
  * the model cannot be reached at all -> AriaLLMError propagates.

Never invent a confidence value.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from llm.config import Role
from llm.llm_setup import invoke_role

logger = logging.getLogger(__name__)

__all__ = ["Judgment", "judge_answer"]

JUDGE_PROMPT = """You are a quality judge for a medical assistant's answers. Evaluate the ANSWER based on two criteria:
1. GROUNDEDNESS: Is the answer supported by the CONTEXT? (not made up)
2. RELEVANCE: Does the answer actually address the QUESTION?

CONTEXT:
{context}

QUESTION: {query}

ANSWER: {answer}

Respond ONLY in this exact JSON format:
{{"confidence": <number between 0 and 1>, "reason": "<short explanation>"}}"""


@dataclass(frozen=True)
class Judgment:
    """The Judge's verdict. `confidence is None` means "not adjudicated"."""

    confidence: float | None
    reason: str

    @property
    def adjudicated(self) -> bool:
        """True only when a real score was parsed from the model's reply."""
        return self.confidence is not None


def _parse(raw: str) -> Judgment:
    """Extract a judgment from the model's reply, or report it unparseable.

    The model occasionally wraps the JSON in prose or a ```json fence, so
    the object is located rather than assumed to be the whole response.
    """
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match is None:
        return Judgment(None, "Judge reply contained no JSON object")

    try:
        parsed: Any = json.loads(match.group(0))
        confidence = float(parsed["confidence"])
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return Judgment(None, "Judge reply could not be parsed as a score")

    reason = parsed.get("reason") if isinstance(parsed, dict) else None
    return Judgment(
        confidence=max(0.0, min(1.0, confidence)),
        reason=str(reason) if reason else "(no reason given)",
    )


def judge_answer(query: str, answer: str, chunks: list[Any]) -> Judgment:
    """Score `answer` against the passages it was supposed to be grounded in.

    Raises:
        AriaLLMError: if the judge model cannot be reached.
    """
    context = "\n\n".join(chunk.page_content for chunk in chunks)
    raw = invoke_role(
        Role.JUDGE,
        JUDGE_PROMPT.format(context=context, query=query, answer=answer),
    )

    judgment = _parse(raw)
    if judgment.adjudicated:
        logger.info("judge confidence: %s - %s", judgment.confidence, judgment.reason)
    else:
        logger.warning("judge produced no usable score: %s", judgment.reason)
    return judgment


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    from agents.navigator_agent import navigator
    from llm.generator import generate_answer

    demo_query = (
        "My mother is 50 and has had diabetes for seven years. She is on oral "
        "hypoglycaemics but her post-lunch sugar rises to 200. What lifestyle "
        "modifications can help?"
    )

    print("── Step 1: Navigate ──")
    demo_chunks = navigator(demo_query)

    print("\n── Step 2: Generate ──")
    demo_answer = generate_answer(demo_query, demo_chunks)
    print(f"\nAnswer: {demo_answer[:1000]}...")

    print("\n── Step 3: Judge ──")
    verdict = judge_answer(demo_query, demo_answer, demo_chunks)

    print("\n── Verdict ──")
    if not verdict.adjudicated:
        print("Answer NOT ADJUDICATED — no confidence available")
    elif verdict.confidence is not None and verdict.confidence >= 0.7:
        print("Answer PASSED — send to user")
    else:
        print("Answer WEAK — retry")
