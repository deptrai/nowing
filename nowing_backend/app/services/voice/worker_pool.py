"""VoiceWorkerPool — manages N OS-level Voice Agent Worker processes.

Story 38.2: Spawns ``VOICE_WORKER_PROCESSES`` (default 8) independent worker
processes, each running ``run_worker()`` — a LiveKit Agents CLI event loop.

Design rationale for multiprocessing (not threading):
- Python's GIL serialises CPU-bound audio work (VAD inference, PCM resampling)
  within a single process. With 12-15 concurrent calls per worker, thread-based
  concurrency causes event-loop lag that pushes perceived latency past 800ms.
- Each ``multiprocessing.Process`` has its own GIL and event loop, so 8 workers
  genuinely parallelise VAD/TTS across cores.

Shutdown protocol:
- ``shutdown()`` sends SIGTERM to every worker then waits ``join(timeout=10)``.
- Workers that don't exit in time receive SIGKILL.
- The pool is designed to run as a child of the main FastAPI process or as a
  standalone ``python -m app.services.voice.worker_pool`` process.
"""

from __future__ import annotations

import contextlib
import logging
import multiprocessing
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from app.config import VOICE_MAX_CALLS_PER_WORKER, VOICE_WORKER_PROCESSES

logger = logging.getLogger(__name__)


@dataclass
class WorkerHandle:
    """Book-keeping for a spawned worker process."""

    worker_id: int
    process: multiprocessing.Process
    started_at: float = field(default_factory=time.monotonic)

    @property
    def pid(self) -> int | None:
        return self.process.pid

    def is_alive(self) -> bool:
        return self.process.is_alive()


class VoiceWorkerPool:
    """Spawns and supervises ``VOICE_WORKER_PROCESSES`` Voice Agent workers.

    Usage::

        pool = VoiceWorkerPool()
        pool.spawn_workers()          # starts all workers
        # ... application runs ...
        pool.shutdown()               # SIGTERM all + join

    Each worker calls ``run_worker()`` which internally runs the LiveKit
    Agents CLI loop (``cli.run_app``), blocking until signalled.
    """

    def __init__(
        self,
        num_workers: int | None = None,
        max_calls_per_worker: int | None = None,
    ) -> None:
        self.num_workers = num_workers or VOICE_WORKER_PROCESSES
        self.max_calls_per_worker = (
            max_calls_per_worker or VOICE_MAX_CALLS_PER_WORKER
        )
        self._workers: dict[int, WorkerHandle] = {}
        self._shutdown_event = multiprocessing.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def spawn_workers(self) -> list[WorkerHandle]:
        """Spawn ``num_workers`` OS processes running the voice agent loop.

        Returns:
            List of WorkerHandle objects for monitoring.

        Raises:
            RuntimeError: If called while workers are already running.
        """
        if self._workers:
            raise RuntimeError("Workers already spawned — call shutdown() first")

        logger.info(
            "Spawning %d voice worker processes (max %d calls each)",
            self.num_workers,
            self.max_calls_per_worker,
        )

        for i in range(self.num_workers):
            handle = self._spawn_worker(i)
            self._workers[i] = handle
            logger.info(
                "Worker %d spawned: pid=%d", i, handle.pid or -1
            )

        return list(self._workers.values())

    def shutdown(self, timeout: float = 10.0) -> None:
        """Gracefully stop all workers.

        Sends SIGTERM to each worker process, then joins with *timeout*.
        Any worker still alive after the timeout is SIGKILLed.

        Args:
            timeout: Seconds to wait for each worker to exit cleanly.
        """
        logger.info("Shutting down %d voice workers", len(self._workers))

        for handle in self._workers.values():
            if handle.is_alive() and handle.pid:
                with contextlib.suppress(ProcessLookupError):
                    os.kill(handle.pid, signal.SIGTERM)

        deadline = time.monotonic() + timeout
        for handle in self._workers.values():
            remaining = max(0.0, deadline - time.monotonic())
            handle.process.join(timeout=remaining)
            if handle.is_alive():
                logger.warning(
                    "Worker %d (pid=%s) did not exit in time — SIGKILL",
                    handle.worker_id,
                    handle.pid,
                )
                handle.process.kill()
                handle.process.join(timeout=2.0)

        self._workers.clear()
        logger.info("All voice workers stopped")

    def is_alive(self, worker_id: int) -> bool:
        """Return True if the worker with *worker_id* is still running.

        Args:
            worker_id: Index assigned at spawn time (0..num_workers-1).
        """
        handle = self._workers.get(worker_id)
        return handle is not None and handle.is_alive()

    def alive_count(self) -> int:
        """Return number of workers currently alive."""
        return sum(1 for h in self._workers.values() if h.is_alive())

    def health(self) -> dict:
        """Return a health summary dict for monitoring endpoints."""
        return {
            "total_workers": self.num_workers,
            "alive_workers": self.alive_count(),
            "max_calls_per_worker": self.max_calls_per_worker,
            "workers": {
                wid: {"pid": h.pid, "alive": h.is_alive()}
                for wid, h in self._workers.items()
            },
        }

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> VoiceWorkerPool:
        self.spawn_workers()
        return self

    def __exit__(self, *args: Any) -> None:
        self.shutdown()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _spawn_worker(self, worker_id: int) -> WorkerHandle:
        """Fork a new worker process.

        Args:
            worker_id: Integer ID used for logging and env tagging.

        Returns:
            WorkerHandle for the spawned process.
        """
        proc = multiprocessing.Process(
            target=_worker_main,
            args=(worker_id,),
            name=f"voice-worker-{worker_id}",
            daemon=False,
        )
        proc.start()
        return WorkerHandle(worker_id=worker_id, process=proc)


def _worker_main(worker_id: int) -> None:
    """Entry point for each spawned worker process.

    Configures a per-process logger then delegates to run_worker().

    Args:
        worker_id: Integer worker index (0-based).
    """
    # Re-configure logging inside the child process
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [worker-{worker_id}] %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger(f"voice.worker.{worker_id}")
    log.info("Voice worker %d starting (pid=%d)", worker_id, os.getpid())

    # Set per-worker env tag for observability
    os.environ["VOICE_WORKER_ID"] = str(worker_id)

    try:
        from app.services.voice.agent_worker import run_worker

        run_worker()
    except SystemExit as exc:
        log.info("Worker %d exited with code %s", worker_id, exc.code)
    except Exception:
        log.exception("Worker %d crashed", worker_id)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI entry point: python -m app.services.voice.worker_pool
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the pool as a standalone process.

    Usage::

        python -m app.services.voice.worker_pool

    Blocks until SIGTERM/SIGINT, then shuts down all workers.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    pool = VoiceWorkerPool()
    pool.spawn_workers()

    def _sigterm(signum: int, frame: object) -> None:
        logger.info("Received signal %d — shutting down", signum)
        pool.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGINT, _sigterm)

    # Keep parent alive and monitor worker health
    try:
        while True:
            time.sleep(5)
            alive = pool.alive_count()
            if alive < pool.num_workers:
                logger.warning(
                    "%d/%d workers alive — %d dead",
                    alive,
                    pool.num_workers,
                    pool.num_workers - alive,
                )
    except KeyboardInterrupt:
        pool.shutdown()


if __name__ == "__main__":
    main()
