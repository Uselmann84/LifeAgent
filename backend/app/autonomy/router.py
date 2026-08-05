"""Environment-aware LLM router (Section 35.6).

Selects a model *profile* for each task based on the execution mode:

* **Production (Backend Mac)** — local reasoning model for planning/consequential drafting, a fast
  local model for classification/extraction, an embedding model, and an optional remote fallback
  (only if explicitly enabled).
* **Simulation (Development Mac)** — deterministic/stubbed responses and smaller/cached profiles;
  no remote API calls unless explicitly enabled.

The router never hard-codes raw model ids in callers; it maps :class:`TaskType` to a profile name
that the provider resolves.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.llm.base import LLMRequest, LLMResponse, TaskType
from app.agent.llm.factory import get_llm_provider
from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class RouteDecision:
    profile: str
    provider: str
    remote_allowed: bool
    reason: str


# Task → profile name, per execution mode. Profiles are resolved by the provider.
_PRODUCTION_ROUTES: dict[TaskType, str] = {
    TaskType.reasoning: "production-reasoning",
    TaskType.classification: "production-fast",
    TaskType.summarization: "production-fast",
    TaskType.extraction: "production-fast",
    TaskType.embedding: "production-embedding",
    TaskType.document: "production-document",
}

_SIMULATION_ROUTES: dict[TaskType, str] = {
    TaskType.reasoning: "development-full",
    TaskType.classification: "development-fast",
    TaskType.summarization: "development-fast",
    TaskType.extraction: "development-fast",
    TaskType.embedding: "development-embedding",
    TaskType.document: "development-document",
}


class LLMRouter:
    """Chooses a profile per task and dispatches to the configured provider."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._provider = get_llm_provider()

    @property
    def provider_name(self) -> str:
        return getattr(self._provider, "name", "unknown")

    def route(self, task_type: TaskType) -> RouteDecision:
        settings = self._settings
        if settings.is_production_execution:
            profile = _PRODUCTION_ROUTES.get(task_type, "production-reasoning")
            remote = settings.feature_remote_ai_fallback
            reason = "production execution: local model with optional remote fallback"
        else:
            profile = _SIMULATION_ROUTES.get(task_type, "development-full")
            # No remote calls from the Development Mac unless explicitly enabled.
            remote = settings.feature_remote_ai_fallback
            reason = "simulation execution: local/stubbed model, no remote unless enabled"
        return RouteDecision(
            profile=profile,
            provider=self.provider_name,
            remote_allowed=remote,
            reason=reason,
        )

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Resolve the profile for the request's task type, then generate."""
        decision = self.route(request.task_type)
        routed = LLMRequest(
            prompt=request.prompt,
            task_type=request.task_type,
            system=request.system,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            profile=decision.profile,
            metadata={**request.metadata, "route_reason": decision.reason},
        )
        return await self._provider.generate(routed)


def get_router(settings: Settings | None = None) -> LLMRouter:
    return LLMRouter(settings)
