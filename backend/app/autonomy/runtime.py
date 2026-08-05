"""Continuous background intelligence loop (Sections 28.1 & 35.2).

The runtime supervises the six autonomous components as one process on the Backend Mac:

    email_monitor · llm_router · memory_manager · decision_engine · notification_dispatcher
    (all coordinated by) agent_loop

Each tick it polls the event sources, runs the decision engine, updates memory, and dispatches
notifications. It supports a one-shot :meth:`tick` (used by tests and the API), a long-running
:meth:`run` with graceful shutdown, structured per-tick logging, and a :meth:`status` health
snapshot. No real-world side effect can occur unless the process runs on the Backend Mac in
production execution mode — the execution boundary enforces this regardless of the loop.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from sqlmodel import Session

from app.autonomy.decision import Decision, DecisionEngine
from app.autonomy.events import EventSource
from app.autonomy.memory import build_memory_manager
from app.autonomy.notifications import NotificationDispatcher
from app.autonomy.router import get_router
from app.autonomy.sources import build_event_sources
from app.core.config import Settings, get_settings
from app.core.models import utcnow

logger = logging.getLogger("lifeagent.autonomy")


@dataclass
class ComponentHealth:
    name: str
    healthy: bool = True
    detail: str = "ok"


@dataclass
class RuntimeStatus:
    execution_mode: str
    running: bool
    ticks: int
    events_processed: int
    last_tick_at: str | None
    components: list[ComponentHealth] = field(default_factory=list)
    side_effects_permitted: bool = False


class AutonomousRuntime:
    """Supervises the autonomous components and runs the continuous loop."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._sources: list[EventSource] = build_event_sources(session, self._settings)
        self._memory = build_memory_manager(session, self._settings)
        self._notifier = NotificationDispatcher(settings=self._settings)
        self._router = get_router(self._settings)
        self._engine = DecisionEngine(session, self._memory, self._notifier, self._settings)

        self._running = False
        self._ticks = 0
        self._events_processed = 0
        self._last_tick_at: str | None = None
        self._stop = asyncio.Event()

    # --- one tick ---------------------------------------------------------------
    def tick(self) -> list[Decision]:
        """Poll every source once and process the resulting events. Returns decisions."""
        from app.autonomy.execution import side_effects_permitted

        limit = self._settings.autonomy_max_events_per_tick
        decisions: list[Decision] = []
        for source in self._sources:
            try:
                events = source.poll(limit)
            except NotImplementedError:
                # Production source whose integration has not landed yet: skip cleanly.
                continue
            for event in events:
                decisions.append(self._engine.decide(event))
                self._events_processed += 1
        self._ticks += 1
        self._last_tick_at = utcnow().isoformat()
        logger.info(
            "autonomy.tick",
            extra={
                "tick": self._ticks,
                "events": len(decisions),
                "execution_mode": self._settings.execution_mode.value,
                "side_effects_permitted": side_effects_permitted(self._settings),
            },
        )
        return decisions

    # --- continuous loop --------------------------------------------------------
    async def run(self) -> None:
        """Run until :meth:`stop` is called. Auto-restart is handled by launchd."""
        self._running = True
        self._stop.clear()
        interval = self._settings.autonomy_loop_interval_seconds
        logger.info("autonomy.start execution_mode=%s", self._settings.execution_mode.value)
        try:
            while not self._stop.is_set():
                self.tick()
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=interval)
                except TimeoutError:
                    pass
        finally:
            self._running = False
            logger.info("autonomy.stopped ticks=%d", self._ticks)

    def stop(self) -> None:
        """Request graceful shutdown."""
        self._stop.set()

    # --- health -----------------------------------------------------------------
    def status(self) -> RuntimeStatus:
        from app.autonomy.execution import side_effects_permitted

        components = [
            ComponentHealth("agent_loop", True, f"{self._ticks} ticks"),
            ComponentHealth("email_monitor", True, f"{len(self._sources)} sources"),
            ComponentHealth("llm_router", True, self._router.provider_name),
            ComponentHealth(
                "memory_manager",
                True,
                "persistent" if self._memory.persistent else "ephemeral",
            ),
            ComponentHealth("decision_engine", True, "ready"),
            ComponentHealth(
                "notification_dispatcher",
                True,
                f"{len(self._notifier.recent())} recent",
            ),
        ]
        return RuntimeStatus(
            execution_mode=self._settings.execution_mode.value,
            running=self._running,
            ticks=self._ticks,
            events_processed=self._events_processed,
            last_tick_at=self._last_tick_at,
            components=components,
            side_effects_permitted=side_effects_permitted(self._settings),
        )
