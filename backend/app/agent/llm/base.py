"""LLM provider protocol and shared request/response types.

The agent depends only on this interface. Concrete providers (mock, ollama, openai_compatible,
mlx, optional remote fallback) implement it. Model selection uses profile names
(e.g. 'production-reasoning'), never hard-coded model strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class TaskType(str, Enum):
    reasoning = "reasoning"
    classification = "classification"
    summarization = "summarization"
    extraction = "extraction"
    embedding = "embedding"
    document = "document"


@dataclass
class LLMRequest:
    prompt: str
    task_type: TaskType = TaskType.reasoning
    system: str | None = None
    max_tokens: int = 512
    temperature: float = 0.2
    # Profile name resolved by the provider/router; not a raw model id.
    profile: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    text: str
    model: str
    profile: str | None
    task_type: TaskType
    latency_ms: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass
class ModelHealth:
    provider: str
    reachable: bool
    profiles_loaded: list[str]
    latency_ms: float | None
    detail: str


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def generate(self, request: LLMRequest) -> LLMResponse: ...

    async def stream(self, request: LLMRequest): ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def health_check(self) -> ModelHealth: ...
