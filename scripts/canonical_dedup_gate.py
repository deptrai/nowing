#!/usr/bin/env python3
"""Release gate for Story 13.2e canonical dedup.

Runs the BDS and Jobs fixtures at 15%, 30% and 70% overlap through the
Nowing eval harness and exits non-zero if any hard gate is not met.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    nowing_evals = repo_root / "nowing_evals"
    env = {**os.environ, "PYTHONPATH": "src"}

    failures: list[str] = []
    for domain in ("bds", "jobs"):
        for overlap in ("15", "30", "70"):
            fixture = f"{domain}-overlap-{overlap}"
            print(f"\n--- canonical dedup gate: {domain} {fixture} ---")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nowing_evals",
                    "run",
                    "canonical",
                    "dedup",
                    "--domain",
                    domain,
                    "--fixture",
                    fixture,
                ],
                cwd=nowing_evals,
                env=env,
            )
            if result.returncode != 0:
                failures.append(f"{domain}/{fixture}")

    if failures:
        print("\n[FAIL] Canonical dedup gate failed for:", ", ".join(failures))
        return 1

    print("\n[PASS] All canonical dedup gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
