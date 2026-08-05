"""Shared API dependencies: DB session, auth, and the caller's role context.

Phase 1 uses a dev shared bearer token (Demo Mode). Production replaces this with per-device paired
credentials minted during pairing (see docs/NETWORK_AND_PAIRING.md). Roles are enforced per route
so a deployment credential can never approve agent actions and an iPhone token can never deploy.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.db import get_session as _get_session
from app.core.models import DeviceRole
from app.security.roles import require_capability


def get_session() -> Iterator[Session]:
    yield from _get_session()


@dataclass
class CallerContext:
    device_id: str
    role: DeviceRole


def get_caller(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> CallerContext:
    """Authenticate the caller and resolve its role.

    In Demo/dev, a valid bearer equal to the dev token authenticates as the owner (who can act as
    the primary user). Production validates a per-device signed credential and returns its stored
    role.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer credential"
        )
    token = authorization.split(" ", 1)[1].strip()
    if token != settings.dev_api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credential")
    # Demo/dev caller acts as owner (primary user).
    return CallerContext(device_id="dev-owner", role=DeviceRole.owner)


def require(capability: str):
    """Route dependency factory enforcing a role capability."""

    def _dep(caller: CallerContext = Depends(get_caller)) -> CallerContext:
        try:
            require_capability(caller.role, capability)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        return caller

    return _dep
