"""
Generator — synthesises the answer from retrieved passages only.

Returns grounded prose or raises. It must never return an error string:
the whole point of the error taxonomy is that the caller can tell the
difference between an answer and a failure without inspecting the text.

It also refuses to run on an empty passage set. The navigator already
raises in that case; this is the second lock on the same door, because the
cost of it failing open is an answer written from the model's own memory
and presented with ARIA's citation furniture around it.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from llm.config import Role
from llm.errors import EMPTY_RETRIEVAL_CODE, AriaRetrievalError
from llm.llm_setup import stream_role
from llm.prompts import ANSWER_PROMPT

logger = logging.getLogger(__name__)

__all__ = ["generate_answer", "stream_answer"]


def _prompt_for(query: str, chunks: list[Any]) -> str:
    """Build the grounded prompt, refusing an empty passage set.

    Raises:
        AriaRetrievalError: if `chunks` is empty. Generating from an empty
            context is the one failure mode ARIA exists to prevent.
    """
    if not chunks:
        raise AriaRetrievalError(
            stage="generator",
            source="retrieved passages",
            message="refusing to generate an answer with no source passages",
            code=EMPTY_RETRIEVAL_CODE,
        )

    context = "\n\n".join(chunk.page_content for chunk in chunks)
    return ANSWER_PROMPT.format(context=context, question=query)


def stream_answer(query: str, chunks: list[Any]) -> Iterator[str]:
    """Stream an answer to `query` grounded strictly in `chunks`.

    This is the serving path: fragments reach the reader as the model writes
    them, rather than after the whole answer exists.

    Raises:
        AriaRetrievalError: if `chunks` is empty.
        AriaLLMError: if the generator model (and its fallback) cannot be
            reached. The exception text is never a valid answer.
    """
    yield from stream_role(Role.GENERATOR, _prompt_for(query, chunks))


def generate_answer(query: str, chunks: list[Any]) -> str:
    """Write an answer to `query` grounded strictly in `chunks`.

    The batch form, for callers with nothing to stream to (the eval suite,
    the CLI entry points). Same prompt and same guarantees as
    `stream_answer` because it is the same call, merely joined up.
    """
    answer = "".join(stream_answer(query, chunks))
    logger.info("generated answer of %d characters from %d chunks", len(answer), len(chunks))
    return answer


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    from agents.navigator_agent import navigator

    demo_query = (
        "my mother is 50 years old and she is having diabetes since last seven years. "
        "She is on oral hypoglycaemic drugs like glycomet gp 1 twice daily and "
        "vildagliptin 50 MG twice daily, but in the morning blood sugar level often "
        "remains increase what we could do to control that?"
    )

    print("Getting chunks from navigator\n")
    demo_chunks = navigator(demo_query)

    print("\n Generating Answer...")
    print("\n=========Answer============")
    print(generate_answer(demo_query, demo_chunks))
