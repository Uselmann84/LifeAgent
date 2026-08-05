"""Version metadata surfaced by the health endpoint and used for compatibility checks."""

from __future__ import annotations

from app import API_VERSION, __version__

BACKEND_VERSION = __version__
API_VERSION = API_VERSION  # noqa: PLW0127 - re-export
DB_SCHEMA_VERSION = 1  # bump with each migration; formatted as e.g. "001"
MIN_COMPATIBLE_IOS_VERSION = "0.1.0"


def schema_version_str() -> str:
    return f"{DB_SCHEMA_VERSION:03d}"
