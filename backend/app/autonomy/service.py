"""Autonomous service supervisor and CLI (Sections 35.2 & 35.9).

The six autonomous services are supervised as components of one process on the Backend Mac:

    agent_loop · email_monitor · llm_router · memory_manager · decision_engine
    · notification_dispatcher

They are installed as a single launchd-managed service
(``infrastructure/launchd/com.lifeagent.autonomy.plist``) which provides auto-start on boot,
auto-restart on failure (KeepAlive), structured logs, and — via the SIGTERM handler below —
graceful shutdown. Health for every component is exposed at ``GET /api/v1/autonomy/status``.

Usage:
    python -m app.autonomy.service run          # run the continuous autonomous runtime
    python -m app.autonomy.service tick         # run a single tick and print decisions (dev)
    python -m app.autonomy.service status       # print a health snapshot as JSON
    python -m app.autonomy.service preflight    # verify the execution boundary before starting
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
from dataclasses import asdict, dataclass

from sqlmodel import Session

from app.autonomy.execution import side_effects_permitted
from app.autonomy.runtime import AutonomousRuntime
from app.core.config import ExecutionMode, get_settings
from app.core.db import engine, run_migrations


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    description: str


# The six logical services, supervised as components of the autonomous runtime.
SERVICE_SPECS: dict[str, ServiceSpec] = {
    "agent_loop": ServiceSpec("agent_loop", "Continuous background intelligence loop"),
    "email_monitor": ServiceSpec("email_monitor", "Email polling + classification event source"),
    "llm_router": ServiceSpec("llm_router", "Environment-aware model routing"),
    "memory_manager": ServiceSpec("memory_manager", "Persistent/ephemeral memory management"),
    "decision_engine": ServiceSpec("decision_engine", "Event → proposed-action decisions"),
    "notification_dispatcher": ServiceSpec("notification_dispatcher", "Proactive user nudges"),
}


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Per-request HTTP client noise (one line per model call) is not useful at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def preflight() -> int:
    """Verify the execution boundary before the runtime starts. Returns a process exit code."""
    settings = get_settings()
    logging.getLogger("lifeagent.autonomy").info(
        "preflight env=%s mode=%s execution_mode=%s side_effects=%s",
        settings.env.value,
        settings.mode.value,
        settings.execution_mode.value,
        side_effects_permitted(settings),
    )
    if settings.execution_mode == ExecutionMode.production and not settings.is_production:
        # Config guardrails already prevent this, but fail closed here too.
        print("preflight FAILED: production execution requires a production environment")
        return 1
    return 0


async def _run_forever() -> None:
    run_migrations()
    with Session(engine) as session:
        runtime = AutonomousRuntime(session)
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, runtime.stop)
        await runtime.run()


def _print_status() -> None:
    run_migrations()
    with Session(engine) as session:
        runtime = AutonomousRuntime(session)
        print(json.dumps(_status_dict(runtime), indent=2, default=str))


def _status_dict(runtime: AutonomousRuntime) -> dict:
    status = runtime.status()
    return {
        "execution_mode": status.execution_mode,
        "running": status.running,
        "ticks": status.ticks,
        "events_processed": status.events_processed,
        "last_tick_at": status.last_tick_at,
        "side_effects_permitted": status.side_effects_permitted,
        "services": [asdict(c) for c in status.components],
    }


def _print_tick() -> None:
    run_migrations()
    with Session(engine) as session:
        runtime = AutonomousRuntime(session)
        decisions = runtime.tick()
        print(json.dumps([asdict(d) for d in decisions], indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(prog="app.autonomy.service")
    parser.add_argument(
        "command",
        choices=["run", "tick", "status", "preflight", "list"],
        help="run the runtime, run one tick, print status, run preflight, or list services",
    )
    args = parser.parse_args(argv)

    if args.command == "list":
        for spec in SERVICE_SPECS.values():
            print(f"{spec.name}: {spec.description}")
        return 0
    if args.command == "preflight":
        return preflight()
    if args.command == "status":
        _print_status()
        return 0
    if args.command == "tick":
        _print_tick()
        return 0
    # run
    code = preflight()
    if code != 0:
        return code
    asyncio.run(_run_forever())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
