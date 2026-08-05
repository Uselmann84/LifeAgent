"""Autonomous agent runtime and the two-Mac execution boundary (Section 35).

This package hosts the autonomous behavior that runs **exclusively on the Backend Mac** in
production execution mode: the continuous intelligence loop, event sources, the environment-aware
LLM router, the memory manager, the decision engine, and the notification dispatcher.

The Development Mac imports the same code but runs it in ``simulation`` execution mode, where every
real-world side effect is refused by :mod:`app.autonomy.execution`.
"""

from __future__ import annotations
