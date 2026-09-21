"""
ARIA failure taxonomy.
------------------------------------------------------------------
The rule this module exists to enforce: a dependency failure is never a
clinical answer.

Before this, an exception's ``str()`` was streamed to the browser through
the same channel as generated prose, so the UI stamped it with an evidence
tier and a "grounded reply" byline. For a clinical decision-support tool
that is not a cosmetic bug — it presents an error string with the visual
authority of adjudicated, cited medical guidance.

So failures travel as their own type, all the way to their own SSE event
and their own UI state. Nothing here ever produces text that could be
mistaken for an answer.

There are two kinds of failure, and they are kept apart because they send
the operator to different places:

  * :class:`AriaLLMError`      — the model provider could not be reached.
  * :class:`AriaRetrievalError` — the evidence base could not be reached,
    or returned nothing to ground an answer in.

Collapsing the second into the first is not cosmetic either: it was
reporting a dead vector store as "failed to reach the language model",
which sent the diagnosis to the wrong subsystem entirely.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "DEAD_MODEL_CODES",
    "EMPTY_RETRIEVAL_CODE",
    "AriaError",
    "AriaLLMError",
    "AriaPreflightError",
    "AriaRetrievalError",
    "AriaStageError",
    "error_code_of",
    "wrap_provider_error",
    "wrap_retrieval_error",
]

#: Provider error codes meaning "this model ID is gone" — the exact
#: condition that took ARIA down when Groq retired llama-3.3-70b-versatile.
#: These are the codes that trigger the fallback model.
DEAD_MODEL_CODES: frozenset[str] = frozenset({"model_not_found", "model_decommissioned"})

#: Retrieval succeeded mechanically but produced no passages. Distinct from a
#: transport failure: the store answered, it just had nothing to say.
EMPTY_RETRIEVAL_CODE: str = "no_passages"


class AriaError(Exception):
    """Base class for every failure ARIA raises deliberately."""


class AriaPreflightError(AriaError):
    """Raised when startup validation finds a configured dependency missing."""


class AriaStageError(AriaError):
    """A pipeline stage could not complete.

    Carries enough structure for the API layer to build an honest error
    event: which stage broke, which dependency, and that dependency's own
    error code. It deliberately does NOT carry anything answer-shaped.
    """

    def __init__(
        self,
        stage: str,
        source: str,
        message: str,
        code: str | None = None,
    ) -> None:
        self.stage = stage
        #: The dependency that failed — a model ID, or a collection name.
        self.source = source
        self.provider_message = message
        self.code = code
        super().__init__(f"[{stage}] {source}: {message}")

    def public_message(self) -> str:
        """A reader-facing sentence. Never mistakable for clinical content."""
        return (
            f"ARIA could not produce an answer: the {self.stage} step failed. "
            "No clinical content was generated."
        )


class AriaLLMError(AriaStageError):
    """An LLM/provider call failed."""

    def __init__(
        self,
        stage: str,
        model: str,
        message: str,
        code: str | None = None,
    ) -> None:
        super().__init__(stage=stage, source=model, message=message, code=code)

    @property
    def model(self) -> str:
        """The model ID that failed. Alias of :attr:`source`."""
        return self.source

    @property
    def is_dead_model(self) -> bool:
        """True when the model ID itself no longer exists at the provider."""
        return self.code in DEAD_MODEL_CODES

    def public_message(self) -> str:
        """Kept free of stack traces and provider jargon: it states that no
        answer was produced and why, and stops there.
        """
        if self.is_dead_model:
            return (
                f"ARIA could not produce an answer: the {self.stage} model "
                f"({self.model}) is no longer available from the provider. "
                "No clinical content was generated."
            )
        return (
            f"ARIA could not produce an answer: the {self.stage} step failed "
            "to reach the language model. No clinical content was generated."
        )


class AriaRetrievalError(AriaStageError):
    """The evidence base failed, or had nothing to ground an answer in.

    Raised instead of falling through to the generator with no passages.
    ARIA's entire claim is that answers come from the retrieved text, so an
    empty retrieval is a failure, not a thin answer.
    """

    @property
    def is_empty(self) -> bool:
        """True when the store was reachable but returned no passages."""
        return self.code == EMPTY_RETRIEVAL_CODE

    def public_message(self) -> str:
        if self.is_empty:
            return (
                "ARIA could not produce an answer: no passages in the reference "
                "library matched this question closely enough to ground one. "
                "No clinical content was generated."
            )
        return (
            "ARIA could not produce an answer: the reference library is "
            "currently unreachable, so no source passages could be retrieved. "
            "No clinical content was generated."
        )


def error_code_of(exc: BaseException) -> str | None:
    """Best-effort extraction of a provider error code.

    Groq's SDK raises ``groq.NotFoundError`` carrying a parsed
    ``body = {"error": {"code": "model_not_found", ...}}``. Other providers
    and transports differ, so fall back to scanning the message for a known
    code rather than assuming a shape.
    """
    body: Any = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            if isinstance(code, str) and code:
                return code

    text = str(exc)
    for known in DEAD_MODEL_CODES:
        if known in text:
            return known
    return None


def wrap_provider_error(exc: BaseException, stage: str, model: str) -> AriaStageError:
    """Normalise any model-provider exception into an :class:`AriaLLMError`.

    An exception that is already one of ARIA's stage errors is returned
    untouched, so a retrieval failure keeps its own identity even when it
    passes through a handler written for provider errors.
    """
    if isinstance(exc, AriaStageError):
        return exc
    return AriaLLMError(
        stage=stage,
        model=model,
        message=str(exc),
        code=error_code_of(exc),
    )


def wrap_retrieval_error(
    exc: BaseException,
    stage: str = "navigator",
    source: str = "vector store",
) -> AriaStageError:
    """Normalise a vector-store/transport exception into a retrieval error."""
    if isinstance(exc, AriaStageError):
        return exc
    return AriaRetrievalError(
        stage=stage,
        source=source,
        message=str(exc),
        code="retrieval_unavailable",
    )
