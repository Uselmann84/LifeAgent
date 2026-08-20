"""Persistent cross-tick dedup of already-processed events (Section 35.5).

Each event source keeps a set of keys it has already emitted so it never surfaces the same email,
task, or message twice. That set is normally per-process, so a manual ``tick``, a launchd restart,
or the next scheduled run would re-emit — and re-notify — the entire inbox. :class:`SeenStore`
persists those keys to a small JSON file under the data dir, namespaced per source, so dedup
survives across processes. Keys are opaque strings; the store never inspects their meaning.
"""

from __future__ import annotations

import json
from pathlib import Path


class SeenStore:
    """Records processed event keys per source, optionally backed by a JSON file.

    With ``path=None`` the store is purely in-memory (per-process), which preserves the original
    behavior for tests and simulation. With a path it loads on construction and writes through on
    every :meth:`add`, so restarts and separate CLI invocations share the same dedup state.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._data: dict[str, set[str]] = {}
        if path is not None:
            try:
                raw = json.loads(path.read_text("utf-8"))
                self._data = {ns: {str(k) for k in keys} for ns, keys in raw.items()}
            except (FileNotFoundError, json.JSONDecodeError):
                self._data = {}

    def seen(self, namespace: str, key: object) -> bool:
        return str(key) in self._data.get(namespace, set())

    def add(self, namespace: str, key: object) -> None:
        self._data.setdefault(namespace, set()).add(str(key))
        self._flush()

    def _flush(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {ns: sorted(keys) for ns, keys in self._data.items()}
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), "utf-8")
        tmp.replace(self._path)
