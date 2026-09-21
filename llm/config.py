"""
ARIA model configuration — the single source of truth for model IDs.
------------------------------------------------------------------
Every LLM, reranker and embedding model used anywhere in ARIA is named
here and nowhere else. Agent code asks for a *role* (guardrail, judge,
generator...) and this module decides which model serves it.

Why a registry instead of a constant: the roles have genuinely different
cost/latency profiles. The guardrail is a one-word YES/NO classifier and
the navigator rewrites a search query — both are well served by the small
model with reasoning turned down. The generator writes the clinical answer
a reader will act on and gets the large model with room to think.

Every value is overridable by environment variable so a model can be
swapped on Hugging Face Spaces without a code change, but every default
is a live model ID — the deployed Space sets no model vars at all and
must keep working on defaults alone.

Verified against Groq's live model list (GET /openai/v1/models) on
2026-08-20; `llm.preflight` re-verifies on every boot.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

__all__ = [
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_FALLBACK_MODEL",
    "DEFAULT_GENERATOR_MODEL",
    "DEFAULT_RERANK_MODEL",
    "DEFAULT_SMALL_MODEL",
    "ModelSpec",
    "Role",
    "all_specs",
    "configured_groq_models",
    "embedding_model",
    "fallback_model",
    "rerank_model",
    "spec_for",
]


class Role(StrEnum):
    """A distinct job in the pipeline, each free to use a different model."""

    GUARDRAIL = "guardrail"
    NAVIGATOR = "navigator"
    GENERATOR = "generator"
    JUDGE = "judge"
    EVAL_JUDGE = "eval_judge"


# ── Defaults ───────────────────────────────────────────────────────────
# The large model reasons in a separate channel that langchain_groq exposes
# as additional_kwargs["reasoning_content"], so `.content` stays clean prose.
# (qwen/qwen3.6-27b is deliberately NOT used: it emits raw <think> blocks
# inline in .content, which would corrupt streamed answers and break the
# judge's JSON parse.)
DEFAULT_GENERATOR_MODEL: Final = "openai/gpt-oss-120b"
DEFAULT_SMALL_MODEL: Final = "openai/gpt-oss-20b"
DEFAULT_FALLBACK_MODEL: Final = "openai/gpt-oss-20b"
DEFAULT_RERANK_MODEL: Final = "rerank-english-v3.0"
DEFAULT_EMBEDDING_MODEL: Final = "all-MiniLM-L6-v2"

# Token budgets are bounded by Groq's per-minute limit, not just by how long
# an answer should be: the on_demand tier allows 8000 TPM on both gpt-oss
# models, and `prompt_tokens + max_tokens` is charged against it up front.
# Measured on a real consultation (5 reranked chunks): prompt ~1543 tokens,
# completion 690-1048. So 4096 leaves ample headroom for a long answer while
# keeping the reservation (1543 + 4096) safely under 8000. Raising this to
# 8192 makes every generator call fail with HTTP 413 before it is even run.
_GENERATOR_MAX_TOKENS: Final = 4096
_JUDGE_MAX_TOKENS: Final = 2048
_SMALL_MAX_TOKENS: Final = 1024


@dataclass(frozen=True)
class ModelSpec:
    """Everything needed to build the LLM client for one role."""

    role: Role
    model: str
    temperature: float
    max_tokens: int
    reasoning_effort: str
    env_var: str

    def describe(self) -> str:
        return (
            f"{self.role.value}={self.model} "
            f"(temp={self.temperature}, max_tokens={self.max_tokens}, "
            f"reasoning={self.reasoning_effort})"
        )


# role -> (env var, default model, temperature, max_tokens, reasoning_effort)
#
# reasoning_effort "low" on the guardrail and navigator is a measured 3x
# latency win (0.94s -> 0.28s on openai/gpt-oss-20b): neither job benefits
# from an extended chain of thought.
_REGISTRY: Final[dict[Role, tuple[str, str, float, int, str]]] = {
    Role.GUARDRAIL: (
        "ARIA_GUARDRAIL_MODEL",
        DEFAULT_SMALL_MODEL,
        0.0,
        _SMALL_MAX_TOKENS,
        "low",
    ),
    Role.NAVIGATOR: (
        "ARIA_NAVIGATOR_MODEL",
        DEFAULT_SMALL_MODEL,
        0.0,
        _SMALL_MAX_TOKENS,
        "low",
    ),
    Role.GENERATOR: (
        "ARIA_GENERATOR_MODEL",
        DEFAULT_GENERATOR_MODEL,
        0.0,
        _GENERATOR_MAX_TOKENS,
        "medium",
    ),
    Role.JUDGE: (
        "ARIA_JUDGE_MODEL",
        DEFAULT_SMALL_MODEL,
        0.0,
        _JUDGE_MAX_TOKENS,
        "medium",
    ),
    Role.EVAL_JUDGE: (
        "ARIA_EVAL_JUDGE_MODEL",
        DEFAULT_SMALL_MODEL,
        0.0,
        _JUDGE_MAX_TOKENS,
        "medium",
    ),
}


def _env(name: str, default: str) -> str:
    """Read an env var, treating blank/whitespace as unset."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def spec_for(role: Role) -> ModelSpec:
    """Resolve the live configuration for one role.

    Read on every call rather than cached at import, so a Space can change
    a secret and a restart is enough — no rebuild.
    """
    env_var, default_model, temperature, max_tokens, effort = _REGISTRY[role]
    return ModelSpec(
        role=role,
        model=_env(env_var, default_model),
        temperature=temperature,
        max_tokens=max_tokens,
        reasoning_effort=effort,
        env_var=env_var,
    )


def all_specs() -> tuple[ModelSpec, ...]:
    """Every configured role, in pipeline order. Used by the preflight."""
    return tuple(spec_for(role) for role in Role)


def fallback_model() -> str:
    """Secondary model used when a primary model is decommissioned."""
    return _env("ARIA_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL)


def rerank_model() -> str:
    """Cohere cross-encoder used by the navigator's reranking step."""
    return _env("ARIA_RERANK_MODEL", DEFAULT_RERANK_MODEL)


def embedding_model() -> str:
    """Sentence-transformers model used for ingestion and query embedding."""
    return _env("ARIA_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def configured_groq_models() -> tuple[str, ...]:
    """Every distinct Groq model ID ARIA might call, including the fallback.

    This is exactly the set the startup preflight validates against the
    provider, so a newly added role can never escape verification.
    """
    seen: dict[str, None] = {}
    for spec in all_specs():
        seen[spec.model] = None
    seen[fallback_model()] = None
    return tuple(seen)
