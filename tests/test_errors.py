"""The failure taxonomy — provider errors must never look like answers."""

from __future__ import annotations

from typing import Any

from llm.errors import (
    AriaLLMError,
    error_code_of,
    wrap_provider_error,
)


class FakeGroqError(Exception):
    """Mirrors groq.NotFoundError: carries a parsed `body`."""

    def __init__(self, code: str) -> None:
        self.body: dict[str, Any] = {
            "error": {
                "message": "The model `x` does not exist or you do not have access to it.",
                "type": "invalid_request_error",
                "code": code,
            }
        }
        super().__init__(f"Error code: 404 - {self.body}")


def test_code_extracted_from_provider_body() -> None:
    assert error_code_of(FakeGroqError("model_not_found")) == "model_not_found"


def test_code_extracted_from_message_when_body_absent() -> None:
    exc = RuntimeError("upstream said model_decommissioned, sorry")
    assert error_code_of(exc) == "model_decommissioned"


def test_unknown_error_has_no_code() -> None:
    assert error_code_of(RuntimeError("connection reset")) is None


def test_dead_model_detection_drives_the_fallback() -> None:
    dead = wrap_provider_error(FakeGroqError("model_not_found"), "generator", "m")
    assert dead.is_dead_model
    alive = wrap_provider_error(RuntimeError("rate limited"), "generator", "m")
    assert not alive.is_dead_model


def test_public_message_is_never_answer_shaped() -> None:
    """The message the reader sees must announce a failure, not advise.

    This is the guard on the original bug: a raw exception string used to be
    streamed as ARIA's grounded clinical reply.
    """
    err = wrap_provider_error(FakeGroqError("model_not_found"), "generator", "dead/model")
    msg = err.public_message()
    assert "could not produce an answer" in msg
    assert "No clinical content was generated." in msg
    # No stack traces, no provider dict spillage.
    assert "Error code:" not in msg
    assert "invalid_request_error" not in msg


def test_wrapping_is_idempotent() -> None:
    original = AriaLLMError("judge", "m", "boom", "some_code")
    assert wrap_provider_error(original, "generator", "other") is original
