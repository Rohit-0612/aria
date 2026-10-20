"""
Context agent — turns a follow-up into a question that stands on its own.

ARIA reads like a conversation, so readers ask the way they would ask a
colleague: "and in pregnancy?", "what dose for renal impairment?". Every
stage downstream of this one sees a single question, though. Retrieval with
"what about its dose" finds nothing about the drug the reader meant, and the
guardrail cannot tell whether "and for children?" is clinical at all.

So a follow-up is rewritten once, here, into a self-contained question, and
everything after it — scope check, retrieval, generation, judging — works on
that. The conversation itself never reaches the generator: the answer is
grounded in retrieved passages only, and earlier replies are not evidence.

The rewrite is a convenience, not a source of content. If the model is
unreachable, the reader's own words are used and a warning is logged — the
same degradation the navigator's query rewrite uses.
"""

from __future__ import annotations

import logging
from typing import TypedDict

from llm.config import Role
from llm.errors import AriaLLMError
from llm.llm_setup import invoke_role

logger = logging.getLogger(__name__)

__all__ = ["MAX_TURN_CHARS", "Turn", "format_history", "resolve_followup"]

#: Earlier replies are clipped before they reach the prompt. The rewrite only
#: needs to know what was being discussed, and a full answer is ~1,000 tokens
#: of a Groq per-minute budget the generator needs more.
MAX_TURN_CHARS = 600


class Turn(TypedDict):
    role: str  # "user" | "assistant"
    content: str


CONTEXT_PROMPT = """You rewrite follow-up questions for a clinical pharmacotherapy search engine.

Given the CONVERSATION so far and a FOLLOW-UP from the user, write the follow-up as one standalone question that can be understood without the conversation. Replace pronouns and vague references ("it", "that drug", "the second option", "and in children?") with the specific drug, condition or patient group they refer to.

If the follow-up is already standalone, or it changes topic, return it unchanged. Never answer the question. Never add facts that the user did not ask about.

CONVERSATION:
{history}

FOLLOW-UP: {query}

Respond with ONLY the standalone question.

Standalone question:"""


def format_history(history: list[Turn]) -> str:
    """Render prior turns for the prompt, clipping long replies."""
    lines: list[str] = []
    for turn in history:
        speaker = "User" if turn["role"] == "user" else "ARIA"
        text = " ".join(turn["content"].split())
        if len(text) > MAX_TURN_CHARS:
            text = text[:MAX_TURN_CHARS].rstrip() + " …"
        lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def resolve_followup(query: str, history: list[Turn]) -> str:
    """Return `query` rewritten to stand alone, given the conversation.

    With no history there is nothing to resolve and no model is called.
    Degrades to `query` unchanged if the model is unavailable or replies
    with nothing usable.
    """
    if not history:
        return query

    try:
        rewritten = invoke_role(
            Role.NAVIGATOR,
            CONTEXT_PROMPT.format(history=format_history(history), query=query),
        ).strip()
    except AriaLLMError as exc:
        logger.warning(
            "Follow-up rewrite unavailable (%s) — using the question as asked",
            exc.code or "provider error",
        )
        return query

    # A rewrite that balloons is the model answering instead of rewriting.
    if not rewritten or len(rewritten) > max(400, 4 * len(query)):
        logger.warning(
            "Follow-up rewrite unusable (%d chars) — using the question as asked", len(rewritten)
        )
        return query

    logger.info("follow-up : %s", query)
    logger.info("standalone: %s", rewritten)
    return rewritten
