"""Run an async coroutine from synchronous code, even inside a running event loop.

The autonomous loop is async, but event sources and the document pipeline are sync and need to call
the async LLM router. Calling ``asyncio.run`` while a loop is already running raises; this bridge
detects that case and runs the coroutine on a short-lived worker thread instead.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Coroutine
from typing import Any


def run_sync[T](coro: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()
