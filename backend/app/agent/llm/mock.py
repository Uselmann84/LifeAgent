"""Deterministic mock LLM provider.

Fully offline. Produces useful, structured, non-random output so the whole app is developable and
testable on the Development Mac without a model server. It never claims to be a real model.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import AsyncIterator

from app.agent.llm.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ModelHealth,
    TaskType,
)

_EMBED_DIM = 64


class MockLLMProvider(LLMProvider):
    name = "mock"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start = time.perf_counter()
        text = self._respond(request)
        latency = (time.perf_counter() - start) * 1000
        return LLMResponse(
            text=text,
            model="mock-deterministic",
            profile=request.profile,
            task_type=request.task_type,
            latency_ms=latency,
            prompt_tokens=len(request.prompt.split()),
            completion_tokens=len(text.split()),
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        response = await self.generate(request)
        for token in response.text.split(" "):
            yield token + " "

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            # Deterministic pseudo-embedding in [0, 1).
            vec = [digest[i % len(digest)] / 255.0 for i in range(_EMBED_DIM)]
            vectors.append(vec)
        return vectors

    async def health_check(self) -> ModelHealth:
        return ModelHealth(
            provider=self.name,
            reachable=True,
            profiles_loaded=["mock-deterministic"],
            latency_ms=1.0,
            detail="Mock provider is always available (offline development).",
        )

    # ------------------------------------------------------------------ internals
    def _respond(self, request: LLMRequest) -> str:
        if request.task_type == TaskType.classification:
            return "informational"
        if request.task_type == TaskType.summarization:
            return "Summary: " + " ".join(request.prompt.split()[:24])
        if request.task_type == TaskType.extraction:
            return "{}"
        # reasoning / document
        return (
            "This is a deterministic mock response. In production this would be produced by the "
            "configured local model. The user-facing rationale is concise and contains no hidden "
            "chain-of-thought."
        )
