"""Non-overlapping work timing for long composed writers (v0.4.59, letter 180).

A recorder is active only inside one writer run (activity-cleanup). Entering a
category pauses the category it is nested in, so the categories never overlap
and, with ``unattributed``, add up to the measured processing time. Only the
thread that started the recorder is measured; work in helper threads is
counted in whatever the starting thread was waiting in. Timing is
observational: it never changes a result and records no paths or content.
"""
from __future__ import annotations

import contextlib
import contextvars
import functools
import threading
import time

_ACTIVE: contextvars.ContextVar["WorkTiming | None"] = contextvars.ContextVar("wom_work_timing", default=None)


class WorkTiming:
    def __init__(self) -> None:
        self.owner = threading.get_ident()
        self.seconds: dict[str, float] = {}
        self.calls: dict[str, int] = {}
        self._stack: list[list] = []

    def _push(self, category: str) -> None:
        now = time.monotonic()
        if self._stack:
            parent = self._stack[-1]
            self.seconds[parent[0]] = self.seconds.get(parent[0], 0.0) + now - parent[1]
        self._stack.append([category, now])
        self.calls[category] = self.calls.get(category, 0) + 1

    def _pop(self) -> None:
        now = time.monotonic()
        category, resumed = self._stack.pop()
        self.seconds[category] = self.seconds.get(category, 0.0) + now - resumed
        if self._stack:
            self._stack[-1][1] = now

    def summary(self, total_seconds: float) -> dict:
        attributed = sum(self.seconds.values())
        return {
            "schema": "wom-kit/work-timing/v1",
            "non_overlapping": True,
            "seconds": {key: round(value, 6) for key, value in sorted(self.seconds.items())},
            "calls": dict(sorted(self.calls.items())),
            "unattributed_seconds": round(max(0.0, total_seconds - attributed), 6),
            "total_seconds": round(total_seconds, 6),
        }


@contextlib.contextmanager
def recording():
    recorder = WorkTiming()
    token = _ACTIVE.set(recorder)
    try:
        yield recorder
    finally:
        _ACTIVE.reset(token)


@contextlib.contextmanager
def measure(category: str):
    recorder = _ACTIVE.get()
    if recorder is None or threading.get_ident() != recorder.owner:
        yield
        return
    recorder._push(category)
    try:
        yield
    finally:
        recorder._pop()


def timed(category: str):
    def decorate(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            if _ACTIVE.get() is None:
                return function(*args, **kwargs)
            with measure(category):
                return function(*args, **kwargs)
        return wrapper
    return decorate
