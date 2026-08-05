"""LLM provider factory. Selects a provider by configuration.

Only the mock provider is fully implemented in Phase 1. Real providers (ollama, openai_compatible,
mlx, remote fallback) are wired here in later phases; requesting one before it is implemented fails
loudly rather than silently degrading.
"""

from __future__ import annotations

from functools import lru_cache

from app.agent.llm.base import LLMProvider
from app.agent.llm.mock import MockLLMProvider
from app.core.config import get_settings


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider == "mock":
        return MockLLMProvider()
    if provider in {"ollama", "openai_compatible", "mlx"}:
        raise NotImplementedError(
            f"LLM provider '{provider}' is not implemented yet (Phase 2+). "
            "Set LIFE_AGENT_LLM_PROVIDER=mock for offline development."
        )
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
