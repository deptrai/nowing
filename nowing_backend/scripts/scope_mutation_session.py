"""Scope a cosmic-ray SQLite session by removing noisy operators.

Usage:
    python scripts/scope_mutation_session.py <session.sqlite>

Removes mutation jobs for operators that are not meaningful for the target
module (e.g., `ReplaceBinaryOperator_BitOr_*` generated from `int | None` type
hints in Python 3.12 syntax). This reduces the denominator and gives a more
accurate mutation score.
"""

from __future__ import annotations

import re
import sqlite3
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scope_mutation_session.py <session.sqlite>")
        return 2

    db_path = sys.argv[1]
    conn = sqlite3.connect(db_path)

    # Operators to remove. These produce false-positive mutations in the target
    # module and do not represent testable logic changes.
    noise_prefixes = ("ReplaceBinaryOperator_BitOr_",)

    cur = conn.cursor()
    cur.execute(
        "SELECT ms.job_id, ms.operator_name "
        "FROM mutation_specs ms "
        "JOIN work_results wr ON wr.job_id = ms.job_id"
    )
    jobs = cur.fetchall()

    removed = 0
    for job_id, operator_name in jobs:
        if operator_name.startswith(noise_prefixes):
            cur.execute("DELETE FROM work_results WHERE job_id = ?", (job_id,))
            cur.execute("DELETE FROM mutation_specs WHERE job_id = ?", (job_id,))
            cur.execute("DELETE FROM work_items WHERE job_id = ?", (job_id,))
            removed += 1

    conn.commit()
    conn.close()

    print(f"Removed {removed} noisy mutation job(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
