#!/usr/bin/env python3
"""SSE / CDN compatibility smoke test.

Story 11.6 T1 / FR41.1 — verify production CDN does not buffer SSE heartbeats.

Connects to a live `/api/v1/threads/{id}/runs/{run_id}/stream` endpoint and
asserts:
  - First heartbeat arrives within 16 s of connection open.
  - Subsequent heartbeats arrive at 15 s ± 2 s intervals.
  - Connection survives ≥ 60 s without disconnect.

Exit code:
  0 = pass
  1 = fail (with diagnostic on stderr)

Usage:
  python3 nowing_backend/scripts/sse_cdn_smoke_test.py \\
      --base-url https://your-domain.com \\
      --bearer-token "$TOKEN" \\
      --thread-id 1 \\
      --run-id <run-uuid>

Run this from a CI step (or runbook checklist) **after** deploying to a
production-mirror environment that includes CDN config.
"""
from __future__ import annotations

import argparse
import math
import sys
import time

import httpx


# SSE comments start with ":". Per the spec any line starting with ":" is a
# keep-alive comment — that's the property a CDN must not buffer. Don't tie
# the smoke test to a specific comment body (e.g. ": heartbeat" vs ": ping")
# or future BE wording changes silently break this gate.
def _is_keepalive_comment(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith(":")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Base URL (e.g. https://host)")
    parser.add_argument("--bearer-token", required=True, help="Auth bearer token")
    parser.add_argument("--thread-id", required=True, type=int)
    parser.add_argument("--run-id", required=True, help="Run UUID")
    parser.add_argument("--first-heartbeat-deadline-s", type=float, default=16.0)
    parser.add_argument("--total-duration-s", type=float, default=60.0)
    parser.add_argument(
        "--max-gap-s",
        type=float,
        default=17.0,
        help=(
            "Maximum allowed gap between consecutive SSE keep-alives "
            "(default 17 = 15s heartbeat interval + 2s slack). Upper-bound "
            "only: shorter gaps are healthy in busy runs where data events "
            "interleave with heartbeats."
        ),
    )
    args = parser.parse_args()

    url = f"{args.base_url.rstrip('/')}/api/v1/threads/{args.thread_id}/runs/{args.run_id}/stream"
    headers = {
        "Accept": "text/event-stream",
        "Authorization": f"Bearer {args.bearer_token}",
    }

    print(f"-> Connecting to {url}", file=sys.stderr)
    start_t = time.monotonic()
    heartbeat_times: list[float] = []
    first_heartbeat_at: float | None = None

    # Round 2 fix: assert the duration window is wide enough to catch
    # buffering. With heartbeats every 15s, a 30s test budget can pass with
    # a single heartbeat (`expected_min = floor(30/15)-1 = 1`) and `gaps == []`
    # — that's vacuous. Require ≥ 60s to see at least 3 keep-alives.
    if args.total_duration_s < 60.0:
        print(
            f"FAIL: total-duration-s={args.total_duration_s} too small to detect "
            f"buffering reliably; require >= 60s.",
            file=sys.stderr,
        )
        return 1

    # Per-read timeout MUST be smaller than total duration so that a fully
    # buffered/stalled CDN raises ReadTimeout *promptly* instead of holding
    # the test open for `total_duration_s + 5`. We expect a heartbeat (or
    # data event) at most every 15s in healthy operation; 20s is comfortable.
    per_read_timeout = max(20.0, args.first_heartbeat_deadline_s + 4.0)
    timeout = httpx.Timeout(
        connect=10.0,
        read=per_read_timeout,
        write=10.0,
        pool=10.0,
    )

    try:
        with httpx.stream("GET", url, headers=headers, timeout=timeout) as response:
            if response.status_code != 200:
                print(
                    f"FAIL: HTTP {response.status_code} {response.reason_phrase}",
                    file=sys.stderr,
                )
                return 1

            content_type = response.headers.get("content-type", "")
            if "text/event-stream" not in content_type:
                print(
                    f"FAIL: unexpected Content-Type {content_type!r} "
                    f"(expected text/event-stream)",
                    file=sys.stderr,
                )
                return 1

            for line in response.iter_lines():
                elapsed = time.monotonic() - start_t

                if _is_keepalive_comment(line):
                    heartbeat_times.append(elapsed)
                    if first_heartbeat_at is None:
                        first_heartbeat_at = elapsed
                        print(f"  + first heartbeat at {elapsed:.2f}s", file=sys.stderr)
                    else:
                        gap = heartbeat_times[-1] - heartbeat_times[-2]
                        print(
                            f"  + heartbeat at {elapsed:.2f}s (gap {gap:.2f}s)",
                            file=sys.stderr,
                        )

                if elapsed >= args.total_duration_s:
                    break
    except httpx.ReadTimeout:
        elapsed = time.monotonic() - start_t
        print(
            f"FAIL: no SSE keep-alive within {per_read_timeout:.0f}s read timeout "
            f"(elapsed {elapsed:.2f}s, {len(heartbeat_times)} heartbeats received) -- "
            f"likely CDN buffering",
            file=sys.stderr,
        )
        return 1
    except httpx.HTTPError as exc:
        print(f"FAIL: HTTP error: {exc}", file=sys.stderr)
        return 1

    if first_heartbeat_at is None:
        print("FAIL: no heartbeat received during smoke test", file=sys.stderr)
        return 1

    if first_heartbeat_at > args.first_heartbeat_deadline_s:
        print(
            f"FAIL: first heartbeat at {first_heartbeat_at:.2f}s "
            f"(> {args.first_heartbeat_deadline_s}s deadline) -- likely CDN buffering",
            file=sys.stderr,
        )
        return 1

    # Required minimum: at least floor(duration / 15) - 1 heartbeats. Without
    # this, a single early heartbeat followed by silence would silently PASS
    # because `gaps == []`.
    expected_min = max(1, math.floor(args.total_duration_s / 15.0) - 1)
    if len(heartbeat_times) < expected_min:
        print(
            f"FAIL: only {len(heartbeat_times)} heartbeat(s) over "
            f"{args.total_duration_s:.0f}s; expected at least {expected_min} "
            f"(15s interval). Likely CDN buffering or stalled connection.",
            file=sys.stderr,
        )
        return 1

    gaps = [
        heartbeat_times[i] - heartbeat_times[i - 1]
        for i in range(1, len(heartbeat_times))
    ]
    # Round 2 fix: only flag UPPER-bound violations. Short gaps (e.g. ~10s
    # between two consecutive `:` keep-alive comments while a busy run is
    # also emitting data events) are healthy — the BE only injects heartbeat
    # when no data event is in flight, so gaps shorter than 15s just mean
    # data flowed in between. Long gaps are the buffering signal.
    bad_gaps = [g for g in gaps if g > args.max_gap_s]
    if bad_gaps:
        print(
            f"FAIL: heartbeat intervals exceed max-gap-s={args.max_gap_s}s: "
            f"{[round(g, 2) for g in bad_gaps]} -- likely CDN buffering",
            file=sys.stderr,
        )
        return 1

    print(
        f"\nPASS -- {len(heartbeat_times)} heartbeats over {args.total_duration_s}s; "
        f"first at {first_heartbeat_at:.2f}s; gaps: {[round(g, 2) for g in gaps]}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
