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
import time
from collections.abc import Callable, Iterator
from typing import Any

from llm.config import Role, generator_cascade, spec_for
from llm.errors import EMPTY_RETRIEVAL_CODE, AriaLLMError, AriaRetrievalError
from llm.gemini import GeminiError, gemini_key, stream_gemini
from llm.llm_setup import stream_role
from llm.prompts import ANSWER_PROMPT, TEACH_PROMPT

logger = logging.getLogger(__name__)

__all__ = ["format_passages", "generate_answer", "passage_label", "printed_page", "stream_answer"]

#: Short names the model cites by. Chunks ingested before the `book` tag
#: existed are all DiPiro, so that is the default.
_BOOK_LABELS = {"dipiro": "DiPiro's Pharmacotherapy 12e", "rxprep": "RxPrep NAPLEX 2025"}


def printed_page(meta: dict[str, Any]) -> Any:
    """The page number printed in the book, which is what a reader looks up.

    DiPiro's chunks carry both the PDF index (`page`, e.g. 1651) and the
    printed label (`page_label`, 1615) — front matter puts them 36 apart, so
    citing the index sent readers to the wrong page. RxPrep was OCR'd page by
    page and has only `page`, which is already the printed number.
    """
    return meta.get("page_label") or meta.get("page")


def passage_label(chunk: Any) -> str:
    """'Book, p. N' for one passage."""
    meta = getattr(chunk, "metadata", {}) or {}
    book = _BOOK_LABELS.get(meta.get("book", "dipiro"), _BOOK_LABELS["dipiro"])
    page = printed_page(meta)
    return f"{book}, p. {page}" if page is not None else book


def format_passages(chunks: list[Any], only: set[int] | None = None) -> str:
    """Number the passages the way the reader will see them.

    Passage `n` here is citation `n` in the UI: both follow the order of
    `chunks`. That shared numbering is the whole contract behind an inline
    `[[n]]` marker opening the passage the claim rests on, so it must not be
    re-sorted anywhere between retrieval and the browser.

    `only` prints a subset (1-based numbers) under their ORIGINAL numbers, for
    a model whose token budget cannot take every passage: a gap in the
    numbering is harmless, a renumbering would point citations at the wrong
    passage.
    """
    return "\n\n".join(
        f"[{i}] {passage_label(chunk)}\n{chunk.page_content.strip()}"
        for i, chunk in enumerate(chunks, start=1)
        if only is None or i in only
    )


#: Groq reserves prompt + max_tokens of its 8,000-token minute up front, and
#: max_tokens is 4,096, so the passages must fit in about 2,600 tokens there.
GROQ_PASSAGE_CHARS = 10_000


def _budget_subset(chunks: list[Any], max_chars: int) -> set[int]:
    """The most relevant passages that fit in `max_chars`, by original number."""
    order = sorted(
        range(len(chunks)),
        key=lambda i: (
            -float((getattr(chunks[i], "metadata", {}) or {}).get("relevance_score", 0.0))
        ),
    )
    keep: set[int] = set()
    used = 0
    for i in order:
        size = len(chunks[i].page_content)
        if keep and used + size > max_chars:
            continue
        keep.add(i + 1)
        used += size
    return keep


def _refuse_empty(chunks: list[Any]) -> None:
    """Generating from an empty context is the one failure mode ARIA exists
    to prevent."""
    if not chunks:
        raise AriaRetrievalError(
            stage="generator",
            source="retrieved passages",
            message="refusing to generate an answer with no source passages",
            code=EMPTY_RETRIEVAL_CODE,
        )


def _prompt_for(
    query: str, chunks: list[Any], outline: list[str] | None = None, only: set[int] | None = None
) -> str:
    """Build the grounded prompt, refusing an empty passage set.

    With an outline it is the teaching prompt; without one, the original
    answer prompt — so switching facet retrieval off restores the old
    pipeline exactly.

    Raises:
        AriaRetrievalError: if `chunks` is empty.
    """
    _refuse_empty(chunks)
    context = format_passages(chunks, only)
    if outline:
        return TEACH_PROMPT.format(
            outline="\n".join(f"- {t}" for t in outline), context=context, question=query
        )
    return ANSWER_PROMPT.format(context=context, question=query)


# ── The Gemini cascade ─────────────────────────────────────────────────
#
# A model that just failed is skipped for a while rather than retried on the
# next question: an exhausted daily quota stays exhausted for hours, and an
# overloaded model costs the reader a timeout each time it is tried.
_COOLDOWN_S = {
    "quota": 30 * 60,
    "overloaded": 3 * 60,
    "network": 60,
    "empty": 60,
    "incomplete": 3 * 60,
    "blocked": 0,
    "bad_request": 30 * 60,
    "unavailable": 12 * 3600,
}
_cooling_until: dict[str, float] = {}


def _available(model: str) -> bool:
    return _cooling_until.get(model, 0.0) <= time.time()


def stream_answer(
    query: str,
    chunks: list[Any],
    outline: list[str] | None = None,
    on_model: Callable[[str], None] | None = None,
    on_restart: Callable[[str], None] | None = None,
) -> Iterator[str]:
    """Stream an answer to `query` grounded strictly in `chunks`.

    With an outline and a Gemini key, the Gemini models in
    `generator_cascade()` are tried in order: a model that is out of quota,
    overloaded, unavailable or blocks the reply is skipped *before* any text
    reaches the reader, and the next one is asked. If none answers, the Groq
    generator writes it from the most relevant passages that fit its token
    budget, keeping their original numbers. `on_model` is told which model
    is writing, before the first fragment.

    A free-tier model can also stop part-way through (it did in 2 of 11
    answers in one eval run). With `on_restart`, that is recovered: the
    caller is told to discard what has streamed, and the next model writes
    the answer from the start. Without it, the failure is raised — a caller
    that cannot take text back must not be handed two answers joined up.

    Raises:
        AriaRetrievalError: if `chunks` is empty.
        AriaLLMError: if every model fails, or one fails mid-answer (a half
            answer is never passed off as a whole one). The exception text is
            never a valid answer.
    """
    _refuse_empty(chunks)
    tried: list[str] = []
    if outline and gemini_key():
        prompt = _prompt_for(query, chunks, outline)
        for model in generator_cascade():
            if not _available(model):
                continue
            try:
                stream = stream_gemini(model, prompt)
                first = next(stream)
            except GeminiError as exc:
                tried.append(f"{model}:{exc.kind}")
                _cooling_until[model] = time.time() + _COOLDOWN_S.get(exc.kind, 60)
                logger.warning("generator %s unavailable (%s) — trying the next model", model, exc)
                continue
            if on_model:
                on_model(model)
            yield first
            try:
                yield from stream
            except GeminiError as exc:
                tried.append(f"{model}:{exc.kind} part-way")
                _cooling_until[model] = time.time() + _COOLDOWN_S.get(exc.kind, 60)
                if on_restart is None:
                    raise AriaLLMError(
                        stage="generator",
                        model=model,
                        message=f"the answer stopped part-way ({exc.kind})",
                        code=f"gemini_{exc.kind}",
                    ) from exc
                logger.warning("generator %s stopped part-way (%s) — rewriting", model, exc)
                on_restart(model)
                continue
            return
        if tried:
            logger.warning("every Gemini model failed (%s) — writing on Groq", ", ".join(tried))

    only = _budget_subset(chunks, GROQ_PASSAGE_CHARS) if outline else None
    if on_model:
        on_model(spec_for(Role.GENERATOR).model)
    yield from stream_role(Role.GENERATOR, _prompt_for(query, chunks, outline, only))


def generate_answer(query: str, chunks: list[Any], outline: list[str] | None = None) -> str:
    """Write an answer to `query` grounded strictly in `chunks`.

    The batch form, for callers with nothing to stream to (the eval suite,
    the CLI entry points). Same prompt and same guarantees as
    `stream_answer` because it is the same call, merely joined up.
    """
    parts: list[str] = []
    for piece in stream_answer(query, chunks, outline, on_restart=lambda _m: parts.clear()):
        parts.append(piece)
    answer = "".join(parts)
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
