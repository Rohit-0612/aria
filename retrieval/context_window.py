"""
Sentence completion — a passage should start and end on a sentence.

The corpus was split into 1,000-character chunks with 200 characters of
overlap, wherever the splitter happened to fall. A retrieved chunk therefore
often opens on half a sentence (". However, for patients with nonmetastatic
castration-resistant ...") and stops on another. The generator reads that
fragment without the subject it refers to, and the reader is shown it as the
evidence.

The points carry no chunk order, only book and page, so the neighbours are
found by the overlap itself: the chunk before shares this chunk's opening
words near its end, the chunk after shares this chunk's closing words near
its start. Only the missing part of the sentence is taken from them (capped),
not the whole neighbour — this is a repair, not a wider window, and it keeps
the prompt inside the Judge's token budget.

One Qdrant request for all pages involved. If it fails, the passages are used
as retrieved: completion improves a passage, it is never a reason to fail a
consultation.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.documents import Document
from qdrant_client.models import FieldCondition, Filter, MatchValue

logger = logging.getLogger(__name__)

__all__ = ["complete_passages", "ends_mid_sentence", "starts_mid_sentence"]

#: The most borrowed from a neighbour on either side.
MAX_EXTENSION = 350
#: How much of this chunk's edge must be found in a neighbour. The splitter's
#: overlap is *up to* 200 characters, so shorter probes are tried in turn;
#: below 25 a match could be coincidence, even within one page.
_PROBES = (60, 40, 25)
_SENTENCE_END = re.compile(r"[.!?][\"')\]]?\s")


def starts_mid_sentence(text: str) -> bool:
    t = text.lstrip()
    return bool(t) and (t[0].islower() or t[0] in ".,;:)]-")


def ends_mid_sentence(text: str) -> bool:
    t = text.rstrip()
    return bool(t) and t[-1] not in ".!?:\"')]"


def _client_and_collection(store: Any) -> tuple[Any, str] | None:
    client = getattr(store, "client", None)
    name = getattr(store, "name", None) or getattr(store, "collection_name", None)
    return (client, name) if client is not None and name else None


def _head_from(prev: str, own_start: str) -> str:
    """The end of the sentence that `prev` was in when this chunk began."""
    at = prev.find(own_start)
    if at <= 0:
        return ""
    before = prev[max(0, at - MAX_EXTENSION) : at]
    ends = list(_SENTENCE_END.finditer(before))
    return before[ends[-1].end() :] if ends else ""


def _tail_from(nxt: str, own_end: str) -> str:
    """The rest of the sentence this chunk stopped in, taken from `nxt`."""
    at = nxt.find(own_end)
    if at < 0:
        return ""
    after = nxt[at + len(own_end) : at + len(own_end) + MAX_EXTENSION]
    end = _SENTENCE_END.search(after)
    return after[: end.end()].rstrip() if end else ""


#: Set once the collection is found to lack a `metadata.page` index (Qdrant
#: Cloud refuses an unindexed filter): neighbours cannot be looked up, so only
#: the local clean-up runs, and the failing request is not repeated per turn.
_NO_PAGE_INDEX = False


def _strip_leading_punctuation(docs: list[Any]) -> list[Any]:
    """ ". CONCLUSION Prostate cancer ..." -> "CONCLUSION Prostate cancer ..."."""
    out: list[Any] = []
    for d in docs:
        body = d.page_content.strip()
        if body[:1] in ".!?;,":
            out.append(Document(page_content=body[1:].lstrip(), metadata=dict(d.metadata)))
        else:
            out.append(d)
    return out


def complete_passages(docs: list[Any], store: Any) -> list[Any]:
    """Return `docs` with half-sentences at either edge completed where possible."""
    global _NO_PAGE_INDEX
    todo = [
        d for d in docs if starts_mid_sentence(d.page_content) or ends_mid_sentence(d.page_content)
    ]
    target = _client_and_collection(store)
    if not todo or target is None:
        return docs
    if _NO_PAGE_INDEX:
        return _strip_leading_punctuation(docs)
    client, collection = target

    pages = {(d.metadata.get("book"), d.metadata.get("page")) for d in todo}
    pages = {(b, p) for b, p in pages if b is not None and p is not None}
    if not pages:
        return docs
    try:
        flt = Filter(
            should=[
                Filter(
                    must=[
                        FieldCondition(key="metadata.book", match=MatchValue(value=b)),
                        FieldCondition(key="metadata.page", match=MatchValue(value=p)),
                    ]
                )
                for b, p in pages
            ]
        )
        points, _ = client.scroll(
            collection,
            scroll_filter=flt,
            limit=12 * len(pages),
            with_payload=True,
            with_vectors=False,
        )
    except Exception as exc:  # noqa: BLE001 - completion is best effort
        if "index required" in str(exc).lower():
            _NO_PAGE_INDEX = True
            logger.warning(
                "sentence completion needs a payload index on metadata.page — "
                "using local clean-up only until one exists"
            )
        else:
            logger.warning("sentence completion skipped (%s)", exc)
        return _strip_leading_punctuation(docs)

    siblings: dict[tuple[Any, Any], list[str]] = {}
    for pt in points:
        payload = pt.payload or {}
        md = payload.get("metadata") or {}
        siblings.setdefault((md.get("book"), md.get("page")), []).append(
            str(payload.get("page_content", ""))
        )

    out: list[Any] = []
    fixed = 0
    for d in docs:
        text = d.page_content
        if not any(d is t for t in todo):
            out.append(d)
            continue
        neighbours = [
            s
            for s in siblings.get((d.metadata.get("book"), d.metadata.get("page")), [])
            if s != text
        ]
        body = text.strip()
        head = tail = ""
        if body[:1] in ".!?;,":
            # ". However, ..." already begins a sentence; only the stray
            # punctuation of the previous one needs to go.
            body = body[1:].lstrip()
        elif starts_mid_sentence(body):
            head = next(
                (h for n in _PROBES for s in neighbours if (h := _head_from(s, body[:n]))), ""
            )
        if ends_mid_sentence(body):
            tail = next(
                (t for n in _PROBES for s in neighbours if (t := _tail_from(s, body[-n:]))), ""
            )
        new = (head.strip() + " " if head.strip() else "") + body + tail
        if new != text.strip():
            fixed += 1
            out.append(Document(page_content=new, metadata=dict(d.metadata)))
        else:
            out.append(d)
    if fixed:
        logger.info("completed the sentences of %d passage(s)", fixed)
    return out
