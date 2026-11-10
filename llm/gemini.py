"""
Gemini client — streaming text from the Gemini API's free tier.

Plain HTTP (server-sent events from `streamGenerateContent`), no SDK: one
endpoint, and the failure modes matter more than convenience, because each
one decides what the generator cascade does next:

  * quota exhausted (429)        -> skip this model until its quota resets
  * overloaded / timeout (503)   -> skip it for a couple of minutes
  * the model is gone (404)      -> skip it for the rest of the process
  * the reply ends without STOP  -> incomplete: treated like a mid-answer
                                    failure, never as a short answer
  * the prompt or reply blocked  -> try the next model; ARIA's own guardrail
                                    has already decided the question is
                                    answerable (toxicology is in scope)

All of them raise `GeminiError` with `retry_next=True` *before* any text is
yielded, so the caller can fall through to another model without the reader
ever seeing a half answer. A failure after text has streamed is raised with
`started=True`; it cannot be retried silently.

Thinking is set low: the passages are given, the job is to organise and
explain them, and a long private chain of thought only adds seconds before
the first word.

The read timeout is short (20 s between streamed events): an overloaded
free-tier model tends to hang rather than refuse, and every second spent
waiting on it is a second the reader waits before the next model is asked.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

import httpx

__all__ = ["GeminiError", "gemini_key", "stream_gemini"]

_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"
)

# The guardrail upstream decides what ARIA answers; Gemini's own filters are
# kept for genuinely high-risk output only, so that overdose management (an
# in-scope teaching topic) is not silently refused.
_SAFETY = [
    {"category": c, "threshold": "BLOCK_ONLY_HIGH"}
    for c in (
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT",
    )
]


class GeminiError(Exception):
    """A Gemini call that produced no usable answer.

    `kind` is one of "quota", "overloaded", "unavailable", "blocked",
    "bad_request", "empty", "incomplete", "network". `started` is True when some text had
    already been yielded before the failure.
    """

    def __init__(self, kind: str, message: str, *, started: bool = False) -> None:
        super().__init__(message)
        self.kind = kind
        self.started = started


def gemini_key() -> str | None:
    key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    return key or None


def _kind_for(status: int, message: str) -> str:
    if status == 429:
        return "quota"
    if status in (500, 502, 503, 504):
        return "overloaded"
    if status == 404:
        return "unavailable"
    if status == 400 and "api key" in message.lower():
        return "unavailable"
    return "bad_request"


def stream_gemini(
    model: str,
    prompt: str,
    *,
    max_output_tokens: int = 8192,
    temperature: float = 0.1,
    thinking_level: str | None = "low",
    timeout_s: float = 20.0,
) -> Iterator[str]:
    """Yield the reply's text as it streams. Raises `GeminiError`."""
    key = gemini_key()
    if key is None:
        raise GeminiError("unavailable", "GEMINI_API_KEY is not set")
    config: dict[str, Any] = {"temperature": temperature, "maxOutputTokens": max_output_tokens}
    if thinking_level:
        config["thinkingConfig"] = {"thinkingLevel": thinking_level}
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": config,
        "safetySettings": _SAFETY,
    }
    started = False
    try:
        with httpx.stream(
            "POST",
            _URL.format(model=model),
            headers={"x-goog-api-key": key},
            json=body,
            timeout=httpx.Timeout(timeout_s, connect=10.0),
        ) as r:
            if r.status_code != 200:
                raw = r.read().decode("utf-8", "replace")
                try:
                    message = json.loads(raw).get("error", {}).get("message", raw)
                except json.JSONDecodeError:
                    message = raw
                raise GeminiError(
                    _kind_for(r.status_code, message), f"{r.status_code}: {message[:300]}"
                )

            finish = None
            for line in r.iter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[5:])
                block = (event.get("promptFeedback") or {}).get("blockReason")
                if block:
                    raise GeminiError("blocked", f"prompt blocked: {block}", started=started)
                for cand in event.get("candidates") or []:
                    for part in (cand.get("content") or {}).get("parts") or []:
                        text = part.get("text")
                        if text and not part.get("thought"):
                            started = True
                            yield text
                    finish = cand.get("finishReason") or finish
            if finish in {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "RECITATION"}:
                raise GeminiError("blocked", f"reply stopped: {finish}", started=started)
            if not started:
                raise GeminiError("empty", f"no text in reply (finish={finish})")
            # A whole reply ends with finishReason STOP. A stream that simply
            # closes (seen: 14 words, then nothing, no error) or runs out of
            # tokens is half an answer, and must not be shown as a whole one.
            if finish != "STOP":
                raise GeminiError(
                    "incomplete", f"reply ended early (finish={finish})", started=True
                )
    except httpx.TimeoutException as exc:
        raise GeminiError("overloaded", f"timed out: {exc}", started=started) from exc
    except httpx.HTTPError as exc:
        raise GeminiError("network", f"{type(exc).__name__}: {exc}", started=started) from exc
