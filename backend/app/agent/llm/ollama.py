"""Ollama LLM provider (local model serving on the Backend Mac).

Talks to a locally running Ollama server (``http://127.0.0.1:11434`` by default) over its HTTP API.
Profiles chosen by the router (e.g. ``production-fast``, ``production-reasoning``) are resolved to
concrete Ollama model ids via configuration:

* ``*embed*``  → :attr:`Settings.model_embedding`
* ``*fast*``   → :attr:`Settings.model_fast`
* everything else (reasoning / document) → :attr:`Settings.model_reasoning`

``httpx`` is imported lazily so the base app has no hard dependency on it; install the ``llm`` extra
on the Backend Mac (``pip install -e '.[llm]'``).
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from app.agent.llm.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ModelHealth,
)
from app.core.config import Settings, get_settings

_TIMEOUT_SECONDS = 120.0


class OllamaLLMProvider(LLMProvider):
    name = "ollama"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._base_url = self._settings.llm_base_url.rstrip("/")

    def _model_for(self, profile: str | None) -> str:
        key = (profile or "").lower()
        if "embed" in key:
            return self._settings.model_embedding
        if "fast" in key:
            return self._settings.model_fast
        return self._settings.model_reasoning

    def _client(self):
        try:
            import httpx
        except ModuleNotFoundError as exc:  # pragma: no cover - install-time guard
            raise RuntimeError(
                "The 'ollama' provider requires httpx. Install the llm extra: pip install -e '.[llm]'"
            ) from exc
        return httpx.AsyncClient(base_url=self._base_url, timeout=_TIMEOUT_SECONDS)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        model = self._model_for(request.profile)
        payload = {
            "model": model,
            "prompt": request.prompt,
            "stream": False,
            "options": {"temperature": request.temperature, "num_predict": request.max_tokens},
        }
        if request.system:
            payload["system"] = request.system
        start = time.perf_counter()
        async with self._client() as client:
            resp = await client.post("/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
        latency = (time.perf_counter() - start) * 1000
        return LLMResponse(
            text=(data.get("response") or "").strip(),
            model=model,
            profile=request.profile,
            task_type=request.task_type,
            latency_ms=latency,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        import json

        model = self._model_for(request.profile)
        payload = {
            "model": model,
            "prompt": request.prompt,
            "stream": True,
            "options": {"temperature": request.temperature, "num_predict": request.max_tokens},
        }
        if request.system:
            payload["system"] = request.system
        async with self._client() as client:
            async with client.stream("POST", "/api/generate", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:  # pragma: no cover - defensive
                        continue
                    token = chunk.get("response")
                    if token:
                        yield token

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._settings.model_embedding
        vectors: list[list[float]] = []
        async with self._client() as client:
            for text in texts:
                resp = await client.post("/api/embeddings", json={"model": model, "prompt": text})
                resp.raise_for_status()
                vectors.append(resp.json().get("embedding", []))
        return vectors

    async def health_check(self) -> ModelHealth:
        start = time.perf_counter()
        try:
            async with self._client() as client:
                resp = await client.get("/api/tags")
                resp.raise_for_status()
                models = [m.get("name", "") for m in resp.json().get("models", [])]
        except Exception as exc:  # pragma: no cover - network/health path
            return ModelHealth(
                provider=self.name,
                reachable=False,
                profiles_loaded=[],
                latency_ms=None,
                detail=f"Ollama unreachable at {self._base_url}: {exc}",
            )
        latency = (time.perf_counter() - start) * 1000
        return ModelHealth(
            provider=self.name,
            reachable=True,
            profiles_loaded=models,
            latency_ms=latency,
            detail=f"Ollama reachable at {self._base_url} with {len(models)} model(s).",
        )
