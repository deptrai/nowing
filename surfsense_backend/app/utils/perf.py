"""
Centralized performance monitoring for SurfSense backend.

Provides:
- A shared [PERF] logger used across all modules
- perf_timer context manager for timing code blocks
- perf_async_timer for async code blocks
- system_snapshot() for CPU/memory profiling
- RequestPerfMiddleware for per-request timing
"""

import logging
import os
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any

_perf_log: logging.Logger | None = None


def get_perf_logger() -> logging.Logger:
    """Return the singleton [PERF] logger, creating it once on first call."""
    global _perf_log
    if _perf_log is None:
        _perf_log = logging.getLogger("surfsense.perf")
        _perf_log.setLevel(logging.DEBUG)
        if not _perf_log.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter("%(asctime)s [PERF] %(message)s"))
            _perf_log.addHandler(h)
            _perf_log.propagate = False
    return _perf_log


@contextmanager
def perf_timer(label: str, *, extra: dict[str, Any] | None = None):
    """Synchronous context manager that logs elapsed wall-clock time.

    Usage:
        with perf_timer("[my_func] heavy computation"):
            ...
    """
    log = get_perf_logger()
    t0 = time.perf_counter()
    yield
    elapsed = time.perf_counter() - t0
    suffix = ""
    if extra:
        suffix = " " + " ".join(f"{k}={v}" for k, v in extra.items())
    log.info("%s in %.3fs%s", label, elapsed, suffix)


@asynccontextmanager
async def perf_async_timer(label: str, *, extra: dict[str, Any] | None = None):
    """Async context manager that logs elapsed wall-clock time.

    Usage:
        async with perf_async_timer("[search] vector search"):
            ...
    """
    log = get_perf_logger()
    t0 = time.perf_counter()
    yield
    elapsed = time.perf_counter() - t0
    suffix = ""
    if extra:
        suffix = " " + " ".join(f"{k}={v}" for k, v in extra.items())
    log.info("%s in %.3fs%s", label, elapsed, suffix)


def system_snapshot() -> dict[str, Any]:
    """Capture a lightweight CPU + memory snapshot of the current process.

    Returns a dict with:
      - rss_mb: Resident Set Size in MB
      - cpu_percent: CPU usage % since last call (per-process)
      - threads: number of active threads
      - open_fds: number of open file descriptors (Linux only)
      - asyncio_tasks: number of asyncio tasks currently alive
    """
    import asyncio

    snapshot: dict[str, Any] = {}
    try:
        import psutil

        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        snapshot["rss_mb"] = round(mem.rss / 1024 / 1024, 1)
        snapshot["cpu_percent"] = proc.cpu_percent(interval=None)
        snapshot["threads"] = proc.num_threads()
        try:
            snapshot["open_fds"] = proc.num_fds()
        except AttributeError:
            snapshot["open_fds"] = -1
    except ImportError:
        snapshot["rss_mb"] = -1
        snapshot["cpu_percent"] = -1
        snapshot["threads"] = -1
        snapshot["open_fds"] = -1

    try:
        all_tasks = asyncio.all_tasks()
        snapshot["asyncio_tasks"] = len(all_tasks)
    except RuntimeError:
        snapshot["asyncio_tasks"] = -1

    return snapshot


def log_system_snapshot(label: str = "system_snapshot") -> None:
    """Capture and log a system snapshot."""
    snap = system_snapshot()
    get_perf_logger().info(
        "[%s] rss=%.1fMB cpu=%.1f%% threads=%d fds=%d asyncio_tasks=%d",
        label,
        snap["rss_mb"],
        snap["cpu_percent"],
        snap["threads"],
        snap["open_fds"],
        snap["asyncio_tasks"],
    )
