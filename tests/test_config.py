"""The model registry: defaults, overrides, and preflight coverage."""

from __future__ import annotations

import pytest

from llm.config import (
    DEFAULT_FALLBACK_MODEL,
    DEFAULT_GENERATOR_MODEL,
    DEFAULT_SMALL_MODEL,
    Role,
    all_specs,
    configured_groq_models,
    embedding_model,
    fallback_model,
    rerank_model,
    spec_for,
)


def test_defaults_are_the_verified_live_models() -> None:
    assert spec_for(Role.GENERATOR).model == DEFAULT_GENERATOR_MODEL == "openai/gpt-oss-120b"
    assert spec_for(Role.JUDGE).model == DEFAULT_SMALL_MODEL == "openai/gpt-oss-20b"
    assert spec_for(Role.GUARDRAIL).model == DEFAULT_SMALL_MODEL


def test_no_decommissioned_model_survives_anywhere() -> None:
    """The exact regression that took ARIA down."""
    dead = {"llama-3.3-70b-versatile", "llama-3.1-8b-instant"}
    configured = set(configured_groq_models()) | {rerank_model(), embedding_model()}
    assert not (configured & dead)


def test_generator_uses_the_larger_model_than_guardrail() -> None:
    assert spec_for(Role.GENERATOR).model != spec_for(Role.GUARDRAIL).model


@pytest.mark.parametrize(
    ("role", "var"),
    [
        (Role.GENERATOR, "ARIA_GENERATOR_MODEL"),
        (Role.JUDGE, "ARIA_JUDGE_MODEL"),
        (Role.GUARDRAIL, "ARIA_GUARDRAIL_MODEL"),
        (Role.NAVIGATOR, "ARIA_NAVIGATOR_MODEL"),
        (Role.EVAL_JUDGE, "ARIA_EVAL_JUDGE_MODEL"),
    ],
)
def test_every_role_is_env_overridable(
    role: Role, var: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(var, "vendor/some-new-model")
    assert spec_for(role).model == "vendor/some-new-model"


def test_blank_env_var_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty Space secret must not configure an empty model ID."""
    monkeypatch.setenv("ARIA_GENERATOR_MODEL", "   ")
    assert spec_for(Role.GENERATOR).model == DEFAULT_GENERATOR_MODEL


def test_preflight_set_covers_every_serving_role_plus_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from llm.config import OFFLINE_ROLES

    monkeypatch.setenv("ARIA_GENERATOR_MODEL", "a/one")
    monkeypatch.setenv("ARIA_FALLBACK_MODEL", "a/two")
    configured = configured_groq_models()
    assert "a/one" in configured
    assert "a/two" in configured
    for spec in all_specs():
        if spec.role not in OFFLINE_ROLES:
            assert spec.model in configured
    every = configured_groq_models(include_offline=True)
    assert all(spec.model in every for spec in all_specs())


def test_generator_budget_fits_the_provider_rate_limit() -> None:
    """Groq reserves prompt+max_tokens against an 8000 TPM cap up front.

    A real consultation's prompt measures ~1543 tokens, so anything above
    roughly 6000 here makes every generator call fail with HTTP 413.
    """
    assert spec_for(Role.GENERATOR).max_tokens <= 6000


def test_fallback_defaults_to_the_small_model() -> None:
    assert fallback_model() == DEFAULT_FALLBACK_MODEL


def test_eval_judge_is_a_different_family_from_the_app_judge() -> None:
    """The suite must not be gpt-oss grading gpt-oss."""
    from llm.config import Role, spec_for

    app = spec_for(Role.JUDGE).model
    offline = spec_for(Role.EVAL_JUDGE).model
    assert app.split("/")[0] != offline.split("/")[0]


def test_eval_only_models_do_not_gate_serving_health() -> None:
    from llm.config import Role, configured_groq_models, spec_for

    assert spec_for(Role.EVAL_JUDGE).model not in configured_groq_models()
    assert spec_for(Role.EVAL_JUDGE).model in configured_groq_models(include_offline=True)


def test_reasoning_effort_is_overridable_per_role(monkeypatch: pytest.MonkeyPatch) -> None:
    from llm.config import Role, spec_for

    monkeypatch.setenv("ARIA_EVAL_JUDGE_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("ARIA_EVAL_JUDGE_EFFORT", "high")
    assert spec_for(Role.EVAL_JUDGE).reasoning_effort == "high"
    assert spec_for(Role.JUDGE).reasoning_effort == "medium"
