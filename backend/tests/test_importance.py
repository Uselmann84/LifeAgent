"""Tests for LLM-backed email importance classification and the Ollama provider's profile mapping.

These run offline: the classifier is exercised against the deterministic mock provider (which always
returns ``informational``), and the Ollama provider's profile→model resolution is a pure function
that needs no network.
"""

from __future__ import annotations

from app.agent.importance import _normalize, _parse, classify_email_importance
from app.agent.llm.ollama import OllamaLLMProvider
from app.autonomy.router import get_router
from app.core.config import get_settings
from app.core.models import ImportanceCategory


def test_normalize_maps_known_labels():
    assert _normalize("critical") is ImportanceCategory.critical
    assert _normalize("Needs-Action-Today") is ImportanceCategory.needs_action_today
    assert _normalize('"dangerous"') is ImportanceCategory.dangerous


def test_normalize_falls_back_to_informational():
    assert _normalize("") is ImportanceCategory.informational
    assert _normalize("totally-unknown-label") is ImportanceCategory.informational


def test_parse_handles_json_and_bare_label():
    assert _parse('{"importance": "critical", "why": "wire transfer"}')["importance"] == "critical"
    assert _parse("promotion") == {"importance": "promotion"}
    assert _parse("") == {}


def test_parse_extracts_prose_wrapped_json():
    raw = 'Here is the result: {"importance": "needs_action_today", "calendar": null} done.'
    assert _parse(raw)["importance"] == "needs_action_today"


def test_classify_email_importance_with_mock_provider():
    router = get_router(get_settings())
    triage = classify_email_importance(
        router,
        sender="boss@example.com",
        subject="Please review",
        body="Can you take a look at the attached contract?",
    )
    # Mock provider deterministically returns "informational" for classification.
    assert triage.importance is ImportanceCategory.informational
    assert triage.why == ""
    assert triage.calendar is None


def test_ollama_profile_resolves_to_configured_models():
    settings = get_settings()
    provider = OllamaLLMProvider(settings)
    assert provider._model_for("production-fast") == settings.model_fast
    assert provider._model_for("production-embedding") == settings.model_embedding
    assert provider._model_for("production-reasoning") == settings.model_reasoning
    assert provider._model_for("production-document") == settings.model_reasoning
    assert provider._model_for(None) == settings.model_reasoning
