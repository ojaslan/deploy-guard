"""In-process request telemetry: real traffic numbers without depending on CloudWatch.

Per-instance and in-memory (single-instance setup). Health checks and /metrics are not counted.
"""
import math
import time
from collections import deque
from threading import Lock

WINDOW_SECONDS = 15 * 60
SKIP_PREFIXES = ("/health", "/metrics")
UNHEALTHY_ERROR_RATE = 10.0  # percent of 5xx responses in the window

_events = deque()
_lock = Lock()


def reset():
    with _lock:
        _events.clear()


def record(status: int, duration_ms: float) -> None:
    now = time.time()
    with _lock:
        _events.append((now, status, duration_ms))
        cutoff = now - WINDOW_SECONDS
        while _events and _events[0][0] < cutoff:
            _events.popleft()


def snapshot(minutes: int = 10) -> dict:
    minutes = max(1, min(int(minutes), WINDOW_SECONDS // 60))
    cutoff = time.time() - minutes * 60
    with _lock:
        rows = [e for e in _events if e[0] >= cutoff]
    total = len(rows)
    errors = sum(1 for _, s, _ in rows if s >= 500)
    durations = sorted(d for _, _, d in rows)
    p90 = durations[max(math.ceil(0.9 * total) - 1, 0)] if total else None
    error_rate = round(errors / total * 100, 2) if total else None
    unhealthy = error_rate is not None and error_rate >= UNHEALTHY_ERROR_RATE
    return {
        "source": "app-telemetry",
        "window_minutes": minutes,
        "requests": total,
        "errors_5xx": errors,
        "error_rate": error_rate,
        "latency_ms": round(p90, 1) if p90 is not None else None,
        "health_status": "unhealthy" if unhealthy else "healthy",
    }
