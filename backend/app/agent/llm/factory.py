"""LLM provider factory. Selects a provider by configuration.

The mock provider runs fully offline for development. The ``ollama`` provider serves a local model
on the Backend Mac. Other real providers (openai_compatible, mlx, remote fallback) fail loudly until
implemented rather than silently degrading.
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
    if provider == "ollama":
        from app.agent.llm.ollama import OllamaLLMProvider

        return OllamaLLMProvider(settings)
    if provider in {"openai_compatible", "mlx"}:
        raise NotImplementedError(
            f"LLM provider '{provider}' is not implemented yet (Phase 2+). "
            "Set LIFE_AGENT_LLM_PROVIDER=mock or =ollama."
        )
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
