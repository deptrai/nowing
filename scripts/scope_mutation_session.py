#!/usr/bin/env python3
"""Mark every mutant outside a target scope as SKIPPED in a cosmic-ray session.

Used to narrow a mutation-gate run without re-running `cosmic-ray init`. Two
scoping mechanisms, applied together:

1. `--functions`: only mutants whose `definition_name` is in this set survive
   scoping (others are marked SKIPPED).
2. `--noise-operators`: within the kept functions, additionally skip operators
   that are near-certain to produce equivalent mutants on this codebase --
   specifically `ReplaceBinaryOperator_*` variants, which fire on `int | None`
   style annotations under `from __future__ import annotations` (the `|` is
   parsed as a BinOp but never evaluated at runtime, since the annotation is a
   lazy string). Default: skip all BinaryOperator/UnaryOperator mutants.

Writes directly to the session's `work_results` table via cosmic-ray's own
`WorkDB` / `WorkResult` API (not raw SQL), so the schema stays cosmic-ray's
responsibility.
"""
from __future__ import annotations

import argparse

from cosmic_ray.work_db import use_db
from cosmic_ray.work_item import WorkerOutcome, WorkResult


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("session", help="Path to the cosmic-ray session sqlite file")
    parser.add_argument(
        "--functions",
        default="",
        help="Comma-separated definition_name values to KEEP (others skipped); empty keeps all",
    )
    parser.add_argument(
        "--keep-noise-operators",
        action="store_true",
        help="Do not skip BinaryOperator/UnaryOperator mutants within kept functions",
    )
    args = parser.parse_args()

    keep_functions = {f.strip() for f in args.functions.split(",") if f.strip()} or None
    noise_prefixes = () if args.keep_noise_operators else (
        "core/ReplaceBinaryOperator",
        "core/ReplaceUnaryOperator",
    )

    kept = 0
    skipped_scope = 0
    skipped_noise = 0

    with use_db(args.session) as db:
        for item in db.pending_work_items:
            for mutation in item.mutations:
                definition = mutation.definition_name
                operator = mutation.operator_name

                if keep_functions and definition not in keep_functions:
                    db.set_result(
                        item.job_id,
                        WorkResult(
                            output="scoped-out: outside target functions",
                            worker_outcome=WorkerOutcome.SKIPPED,
                        ),
                    )
                    skipped_scope += 1
                    break

                if noise_prefixes and operator.startswith(noise_prefixes):
                    db.set_result(
                        item.job_id,
                        WorkResult(
                            output=(
                                "scoped-out: operator on a `from __future__ import "
                                "annotations` type-hint BinOp, never evaluated at runtime"
                            ),
                            worker_outcome=WorkerOutcome.SKIPPED,
                        ),
                    )
                    skipped_noise += 1
                    break

                kept += 1
                break

    print(f"kept for exec: {kept}")
    print(f"skipped (outside target functions): {skipped_scope}")
    print(f"skipped (noise operators): {skipped_noise}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
