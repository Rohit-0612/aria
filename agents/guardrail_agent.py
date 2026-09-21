"""
Guardrail agent — decides whether a query is in clinical scope.

A provider failure here is never treated as "in scope". The previous
behaviour of defaulting to allow on error meant a dead LLM silently
disabled the scope filter; now the failure propagates and the consultation
stops with an explicit error state.
"""

from __future__ import annotations

import logging
import re

from llm.config import Role
from llm.llm_setup import invoke_role

logger = logging.getLogger(__name__)

__all__ = ["check_guardrail"]

GUARDRAIL_PROMPT = """You are a guardrail for a medical chatbot based on a pharmacology textbook.

Your job: Decide if the user's question is related to medicine, pharmacology, diseases, drugs, treatments, or health.

Respond with ONLY one word:
- "YES" if it is medical/health related
- "NO" if it is not

User question: {query}

Answer (YES or NO):"""


def check_guardrail(query: str) -> bool:
    """Return True when `query` is a medical/pharmacology question.

    Raises:
        AriaLLMError: if the guardrail model cannot be reached. Callers must
            not interpret this as a pass — an unanswerable guardrail means
            the consultation cannot safely proceed.
    """
    reply = invoke_role(Role.GUARDRAIL, GUARDRAIL_PROMPT.format(query=query))
    decision = reply.strip().upper()

    # First whole word wins. A substring test for "YES" also matched the
    # "yes" inside a hedged refusal ("...the answer is no, yes it's off
    # topic"), and matched nothing predictable when the model added prose.
    verdict = re.search(r"\b(YES|NO)\b", decision)
    if verdict is None:
        # The guardrail cannot vouch for this query, so it is not allowed
        # through — the same conservative direction as an unreachable one.
        logger.warning("Guardrail reply %r has no YES/NO — treating as out of scope", decision)
        return False

    is_medical = verdict.group(1) == "YES"
    logger.info("Guardrail check: %r -> %s", query, verdict.group(1))
    return is_medical


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    test_queries = [
        "what is hypertension?",
        "Tell me about metformin",
        "How to treat diabetes?",
        "What is the capital of France?",
        "Why is the sky blue?",
        "How to cure a cold?",
        "What is the weather today?",
    ]

    print("\nTesting guardrail:")
    for q in test_queries:
        status = "ALLOWED" if check_guardrail(q) else "REJECTED"
        print(f"{status}: {q}")
