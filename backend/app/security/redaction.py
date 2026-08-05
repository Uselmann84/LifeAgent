"""Redaction helpers for logs, audit entries, and error payloads.

Secrets, tokens, and obviously-sensitive identifiers are masked. Audit and logs must never contain
raw secrets, full email bodies, or full sensitive document text.
"""

from __future__ import annotations

import re
from typing import Any

_SECRET_KEYS = {
    "password",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "secret",
    "refresh_token",
    "access_token",
    "master_key",
    "private_key",
    "client_secret",
}

# Coarse patterns for values that should never appear in logs.
_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"),  # long opaque tokens
]

_MASK = "***REDACTED***"


def redact_text(value: str, max_len: int = 280) -> str:
    """Mask token-like substrings and truncate long free text (e.g. email bodies)."""
    redacted = value
    for pattern in _PATTERNS:
        redacted = pattern.sub(_MASK, redacted)
    if len(redacted) > max_len:
        redacted = redacted[:max_len] + "…[truncated]"
    return redacted


def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with secret-named keys masked and text values redacted/truncated."""
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in _SECRET_KEYS:
            out[key] = _MASK
        elif isinstance(value, str):
            out[key] = redact_text(value)
        elif isinstance(value, dict):
            out[key] = redact_mapping(value)
        elif isinstance(value, list):
            out[key] = [redact_mapping(v) if isinstance(v, dict) else v for v in value]
        else:
            out[key] = value
    return out
