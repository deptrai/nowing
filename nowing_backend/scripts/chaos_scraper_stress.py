#!/usr/bin/env python3
"""Anti-Zombie Chaos Testing Harness (AC-2 / AD-108).

Drives the real scraper/browser stack through the hermetic
``POST /api/v1/test/extract-entities`` endpoint in a long-duration loop.
Every 60 seconds it runs ``ps aux`` and counts *all* ``Z`` / ``<defunct>``
processes in the container, not only the script's children.  Exits non-zero
on any zombie and appends snapshots to ``zombie_log.jsonl``.

Usage:
    python3 scripts/chaos_scraper_stress.py --ci --workers 4
    python3 scripts/chaos_scraper_stress.py --duration-seconds 259200 --workers 8
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from typing import TypedDict

import httpx

DEFAULT_DURATION_SECONDS = 72 * 3600
CI_DURATION_SECONDS = 300
DEFAULT_INTERVAL_SECONDS = 30
DEFAULT_WORKERS = 4
DEFAULT_ZOMBIE_LOG = "zombie_log.jsonl"
DEFAULT_BASE_URL = "http://localhost:8000"
ENDPOINT = "/api/v1/test/extract-entities"

_SAMPLE_SOURCE_TEXTS = [
    "Công ty TNHH ABC, MST 0123456789, hotline 0908123456.",
    "Liên hệ Công ty Cổ phần XYZ theo số 0912345678, mã số thuế 0314539064.",
    "Doanh nghiệp tư nhân DEF: 0903123456, MST 2400775144.",
    "Cty TNHH GHI, ĐT 0987654321, MST 0122334455.",
    "Tổng công ty JKL, phone +849081234567, MST 0311223344.",
]


class ChaosHarnessError(Exception):
    """Raised when the harness detects zombies or an unrecoverable failure."""


class _ZombieSnapshot(TypedDict):
    timestamp: str
    elapsed_seconds: float
    zombie_count: int
    zombies: list[dict[str, str]]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Anti-zombie scraper stress harness with container-wide zombie monitoring."
    )
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=None,
        help="Total stress duration in seconds (default: 72h; --ci overrides to 300s).",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: set default duration to 300s unless --duration-seconds is supplied.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Concurrent workers per stress cycle (default: {DEFAULT_WORKERS}).",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        help=f"Sleep between stress cycles in seconds (default: {DEFAULT_INTERVAL_SECONDS}).",
    )
    parser.add_argument(
        "--zombie-log",
        type=str,
        default=DEFAULT_ZOMBIE_LOG,
        help=f"Path to append zombie snapshots as JSONL (default: {DEFAULT_ZOMBIE_LOG}).",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=DEFAULT_BASE_URL,
        help=f"Base URL for the test extraction endpoint (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=10,
        help="Exit non-zero after this many consecutive stress-request failures (default: 10).",
    )
    return parser


def _resolve_duration(args: argparse.Namespace) -> float:
    if args.duration_seconds is not None:
        return float(args.duration_seconds)
    if args.ci:
        return float(CI_DURATION_SECONDS)
    return float(DEFAULT_DURATION_SECONDS)


def _parse_ps_aux(output: str) -> tuple[int, list[dict[str, str]]]:
    """Parse ``ps aux`` output and return (zombie_count, zombie_records).

    A process is classified as a zombie if its ``STAT`` column contains ``Z``
    or its command line contains ``<defunct>`` / ``defunct``.
    """
    lines = output.splitlines()
    if not lines:
        return 0, []

    header = lines[0].split()
    try:
        stat_index = header.index("STAT")
    except ValueError:
        # Fallback: STAT is the 8th column in a canonical ``ps aux`` header.
        stat_index = 7

    zombies: list[dict[str, str]] = []
    zombie_re = re.compile(r"\bdefunct\b|<defunct>", re.IGNORECASE)
    # STAT values containing Z indicate a zombie; sometimes it is followed by
    # additional state flags (e.g. "Z+").
    stat_z_re = re.compile(r"\bZ")

    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue

        fields = stripped.split(None, 10)
        if len(fields) <= stat_index:
            continue

        stat = fields[stat_index] if len(fields) > stat_index else ""
        command = fields[-1] if len(fields) > 10 else ""
        if (
            stat_z_re.search(stat)
            or zombie_re.search(command)
            or zombie_re.search(stripped)
        ):
            pid = fields[1] if len(fields) > 1 else ""
            ppid = fields[2] if len(fields) > 2 else ""
            zombies.append(
                {
                    "pid": pid,
                    "ppid": ppid,
                    "stat": stat,
                    "command": command,
                }
            )

    return len(zombies), zombies


def _check_zombies() -> _ZombieSnapshot:
    """Run ``ps aux`` and return a snapshot of all zombie processes."""
    started = time.perf_counter()
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=10.0,
        )
    except Exception as exc:
        return {
            "timestamp": _now_iso(),
            "elapsed_seconds": 0.0,
            "zombie_count": -1,
            "zombies": [{"error": f"ps aux failed: {exc}"}],
        }

    count, zombies = _parse_ps_aux(result.stdout)
    return {
        "timestamp": _now_iso(),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "zombie_count": count,
        "zombies": zombies,
    }


def _append_zombie_log(log_path: str, snapshot: _ZombieSnapshot) -> None:
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(
            f"Warning: could not append zombie log at {log_path}: {exc}",
            file=sys.stderr,
        )


def _print_zombies(snapshot: _ZombieSnapshot) -> None:
    print(
        f"[{snapshot['timestamp']}] zombie_count={snapshot['zombie_count']} "
        f"elapsed={snapshot['elapsed_seconds']}s"
    )
    for z in snapshot["zombies"][:10]:
        print(
            f"  pid={z.get('pid')} ppid={z.get('ppid')} stat={z.get('stat')} cmd={z.get('command')[:80]!r}"
        )
    if snapshot["zombie_count"] > 10:
        print(f"  ... and {snapshot['zombie_count'] - 10} more")


async def _call_extract_endpoint(
    client: httpx.AsyncClient,
    base_url: str,
    secret: str,
    worker_id: int,
) -> None:
    """POST a synthetic source text to the hermetic extraction endpoint."""
    text = _SAMPLE_SOURCE_TEXTS[worker_id % len(_SAMPLE_SOURCE_TEXTS)]
    url = f"{base_url.rstrip('/')}{ENDPOINT}"
    payload = {"source_text": text, "source_url": None}
    headers = {
        "X-Internal-Test": secret,
        "Content-Type": "application/json",
    }
    response = await client.post(url, json=payload, headers=headers)
    response.raise_for_status()


async def _stress_cycle(
    client: httpx.AsyncClient,
    base_url: str,
    secret: str,
    workers: int,
) -> tuple[int, int]:
    """Run one concurrent stress cycle. Returns (successes, failures)."""
    tasks = [
        asyncio.create_task(_call_extract_endpoint(client, base_url, secret, i))
        for i in range(workers)
    ]
    successes = 0
    failures = 0

    for coro in asyncio.as_completed(tasks, timeout=60.0):
        try:
            await coro
            successes += 1
        except Exception as exc:
            print(f"Stress request failed: {exc}", file=sys.stderr)
            failures += 1

    # Cancel any remaining tasks (defensive; as_completed with timeout cancels).
    for t in tasks:
        if not t.done():
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await t

    return successes, failures


async def _run_stress(args: argparse.Namespace, secret: str) -> int:
    duration = _resolve_duration(args)
    base_url = args.base_url
    zombie_log = args.zombie_log
    workers = max(1, args.workers)
    interval = max(0.0, args.interval_seconds)
    max_consecutive_failures = max(1, args.max_consecutive_failures)

    print(
        f"Starting anti-zombie stress harness: duration={duration}s, "
        f"workers={workers}, interval={interval}s, base_url={base_url}, "
        f"zombie_log={zombie_log}"
    )

    start_time = time.monotonic()
    last_zombie_check = start_time
    consecutive_failures = 0
    failed_zombie = False

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(60.0),
        follow_redirects=True,
    ) as client:
        while True:
            elapsed = time.monotonic() - start_time
            if elapsed >= duration:
                break

            successes, failures = await _stress_cycle(client, base_url, secret, workers)
            if successes == 0 and failures > 0:
                consecutive_failures += 1
            else:
                consecutive_failures = 0

            if consecutive_failures >= max_consecutive_failures:
                print(
                    f"FAIL: {consecutive_failures} consecutive stress cycles produced "
                    "only request failures; aborting.",
                    file=sys.stderr,
                )
                return 1

            now = time.monotonic()
            if now - last_zombie_check >= 60.0:
                snapshot = _check_zombies()
                _append_zombie_log(zombie_log, snapshot)
                _print_zombies(snapshot)
                last_zombie_check = now

                if snapshot["zombie_count"] > 0:
                    print(
                        f"FAIL: Detected {snapshot['zombie_count']} zombie process(es) in container.",
                        file=sys.stderr,
                    )
                    failed_zombie = True
                    # Continue logging for the remainder so the operator has a
                    # complete picture, but the final exit will be non-zero.

            # Sleep the remainder of the interval, accounting for cycle time.
            cycle_elapsed = time.monotonic() - (start_time + elapsed)
            sleep_for = interval - cycle_elapsed
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)

    if failed_zombie:
        print("FAIL: Anti-zombie stress harness completed with zombie(s) detected.")
        return 1

    print("PASS: Anti-zombie stress harness completed with 0 zombies.")
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    secret = os.environ.get("TEST_EXTRACTION_SECRET")
    if not secret:
        print(
            "TEST_EXTRACTION_SECRET must be set to call the hermetic test endpoint",
            file=sys.stderr,
        )
        return 1

    try:
        return asyncio.run(_run_stress(args, secret))
    except KeyboardInterrupt:
        print("Interrupted by user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
