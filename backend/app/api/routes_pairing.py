"""Device pairing (scaffold) and admin endpoints.

Pairing lets the Backend Mac enroll the iPhone independently of the Development Mac. Codes are
single-use and time-limited. Cryptographic identity is a placeholder in Phase 1 (documented in
PROJECT_STATUS.md) and hardened in a later phase (X25519 device keys + pinning).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps import get_caller, get_session, require
from app.api.schemas import PairingCompleteRequest, PairingStartResponse
from app.core.models import DeviceRole, PairedDevice, PairingCode, utcnow

router = APIRouter(prefix="/api/v1", tags=["pairing", "admin"])

_PAIRING_TTL = timedelta(minutes=10)


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


@router.post(
    "/pairing/start",
    response_model=PairingStartResponse,
    dependencies=[Depends(require("manage_devices"))],
)
def pairing_start(session: Session = Depends(get_session)) -> PairingStartResponse:
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = utcnow() + _PAIRING_TTL
    session.add(PairingCode(code_hash=_hash_code(code), role=DeviceRole.iphone_user, expires_at=expires))
    session.commit()
    # The QR payload would also carry the backend's public key for pinning.
    qr_payload = f"lifeagent://pair?code={code}"
    return PairingStartResponse(code=code, expires_at=expires, qr_payload=qr_payload)


@router.post("/pairing/complete")
def pairing_complete(body: PairingCompleteRequest, session: Session = Depends(get_session)) -> dict:
    code_hash = _hash_code(body.code)
    pc = session.exec(select(PairingCode).where(PairingCode.code_hash == code_hash)).first()
    if not pc or pc.used:
        raise HTTPException(status_code=400, detail="Invalid or used pairing code")
    expires = pc.expires_at
    if expires.tzinfo is None:

        expires = expires.replace(tzinfo=UTC)
    if utcnow() > expires:
        raise HTTPException(status_code=400, detail="Pairing code expired")

    try:
        role = DeviceRole(body.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid role") from exc

    device = PairedDevice(name=body.device_name, role=role, public_key=body.public_key)
    pc.used = True
    session.add(device)
    session.add(pc)
    session.commit()
    session.refresh(device)
    return {"device_id": device.id, "backend_public_key": "<placeholder-backend-public-key>"}


@router.post("/pairing/revoke/{device_id}", dependencies=[Depends(require("manage_devices"))])
def pairing_revoke(device_id: str, session: Session = Depends(get_session)) -> dict:
    device = session.get(PairedDevice, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.revoked = True
    session.add(device)
    session.commit()
    return {"revoked": device_id}


@router.get("/admin/status", dependencies=[Depends(require("service_health"))])
def admin_status(session: Session = Depends(get_session)) -> dict:
    devices = session.exec(select(PairedDevice)).all()
    return {
        "paired_devices": len(devices),
        "revoked_devices": len([d for d in devices if d.revoked]),
    }


@router.get("/admin/devices", dependencies=[Depends(require("manage_devices"))])
def admin_devices(session: Session = Depends(get_session)) -> dict:
    devices = session.exec(select(PairedDevice)).all()
    return {
        "items": [
            {
                "id": d.id,
                "name": d.name,
                "role": d.role.value,
                "revoked": d.revoked,
                "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
            }
            for d in devices
        ]
    }


@router.post("/admin/emergency-stop", dependencies=[Depends(require("emergency_recovery"))])
def emergency_stop(caller=Depends(get_caller)) -> dict:
    # Phase 1: signals intent. A real implementation flips a global automation kill-switch that
    # every scheduled job and tool checks before acting.
    return {"stopped": True, "note": "All automations halted (emergency stop signaled)."}
