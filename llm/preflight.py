"""
Startup model validation.
------------------------------------------------------------------
ARIA went down because a model ID silently stopped existing and nothing
noticed until a reader asked a clinical question. This module moves that
discovery to boot time: it asks the provider which models actually exist
and compares that against every model `llm.config` is configured to call.

Default behaviour is to log loudly and keep serving — a dead *primary*
model is survivable because `invoke_role` falls back, and taking the whole
Space down would turn a degraded demo into no demo. Set
ARIA_PREFLIGHT_STRICT=1 to refuse to boot instead.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from groq import Groq

from llm.config import configured_groq_models
from llm.errors import AriaPreflightError

logger = logging.getLogger(__name__)

__all__ = ["PreflightReport", "available_models", "run_preflight", "strict_mode"]


@dataclass(frozen=True)
class PreflightReport:
    """Outcome of one startup validation pass."""

    checked: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    available: tuple[str, ...] = ()
    error: str | None = None
    log_lines: tuple[str, ...] = field(default=())

    @property
    def ok(self) -> bool:
        """True only when every configured model was found at the provider."""
        return not self.missing and self.error is None

    def as_dict(self) -> dict[str, object]:
        """Shape used by /api/health so the check is visible from outside."""
        return {
            "ok": self.ok,
            "checked": list(self.checked),
            "missing": list(self.missing),
            "error": self.error,
        }


def strict_mode() -> bool:
    """Whether a failed preflight should prevent the app from starting."""
    return os.getenv("ARIA_PREFLIGHT_STRICT", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def available_models(client: Groq | None = None) -> set[str]:
    """Model IDs the provider currently serves (GET /openai/v1/models)."""
    groq_client = client if client is not None else Groq()
    return {model.id for model in groq_client.models.list().data}


def run_preflight(client: Groq | None = None) -> PreflightReport:
    """Validate every configured model against the provider's live list.

    Never raises for a *missing model* unless strict mode is on; the report
    carries the outcome so the caller can surface it on /api/health.

    Raises:
        AriaPreflightError: only when strict mode is enabled and the check
            fails, so the process exits rather than serving a broken graph.
    """
    checked = configured_groq_models()

    try:
        live = available_models(client)
    except Exception as exc:  # a probe failure must not crash boot
        message = f"could not reach the model provider: {exc}"
        logger.error("PREFLIGHT: %s", message)
        logger.error(
            "PREFLIGHT: skipping model validation; configured models are %s",
            ", ".join(checked),
        )
        report = PreflightReport(checked=checked, error=message)
        if strict_mode():
            raise AriaPreflightError(f"ARIA preflight failed — {message}") from exc
        return report

    missing = tuple(model for model in checked if model not in live)
    report = PreflightReport(
        checked=checked,
        missing=missing,
        available=tuple(sorted(live)),
    )

    if report.ok:
        logger.info(
            "PREFLIGHT OK: %d configured model(s) verified against the provider — %s",
            len(checked),
            ", ".join(checked),
        )
        return report

    # Loud, greppable, and specific about what to do next.
    logger.critical("=" * 72)
    logger.critical("ARIA PREFLIGHT FAILED — configured model(s) do not exist upstream")
    for model in missing:
        logger.critical("  MISSING: %r is not served by the provider", model)
    logger.critical("  Provider currently serves: %s", ", ".join(sorted(live)))
    logger.critical("  Fix: set the matching ARIA_*_MODEL environment variable to a live ID.")
    logger.critical("=" * 72)

    if strict_mode():
        raise AriaPreflightError(
            "ARIA preflight failed — unavailable model(s): " + ", ".join(missing)
        )
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    from dotenv import load_dotenv

    load_dotenv()
    result = run_preflight()
    print(f"\npreflight ok={result.ok} missing={result.missing}")
