#!/usr/bin/env python3
"""Generate FE plan-ids.ts from BE PlanId enum.

Story 11.6 T3 / ADR-012 — single source of truth for Pro plan SKUs.

The BE schema (`nowing_backend/app/schemas/stripe.py:PlanId`) is canonical.
This script parses that file's AST (no import side-effects) and emits a
TypeScript file that the FE consumes.

Usage:
    python3 scripts/generate_plan_ids.py [--check]

    --check : exit non-zero if the generated file differs from the committed
              version (used in CI as a drift detector).

Output: nowing_web/lib/generated/plan-ids.ts
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BE_SCHEMA = REPO_ROOT / "nowing_backend" / "app" / "schemas" / "stripe.py"
FE_OUTPUT = REPO_ROOT / "nowing_web" / "lib" / "generated" / "plan-ids.ts"


def _extract_string_literal(value: ast.expr) -> str | None:
    """Pull a string literal out of an expression we accept as the plan's value.

    Supports:
    - Plain literals: `"pro_monthly"`
    - Pydantic-style Field calls: `Field("pro_monthly", description="...")` —
      we read the FIRST positional arg.

    Returns the string, or None if the shape isn't recognized (caller decides
    whether to fail).
    """
    # Plain literal.
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value

    # `Field("plan_id", ...)` — accept any callable name with a string-literal
    # first positional arg. Common Pydantic pattern that BE engineers may
    # reach for to attach metadata; we don't want it to hard-fail codegen
    # for every BE PR.
    if (
        isinstance(value, ast.Call)
        and value.args
        and isinstance(value.args[0], ast.Constant)
        and isinstance(value.args[0].value, str)
    ):
        return value.args[0].value

    return None


def extract_plan_ids(schema_path: Path) -> list[str]:
    """Parse the BE PlanId enum and return the list of SKU values.

    Preserves declaration order from the source (NOT alphabetised) so any
    downstream code depending on enum order (e.g. UI default selection,
    pricing-tier ladder) sees the same sequence in BE and FE.

    Raises if any class member is not a plain `name = "literal"` Assign or
    AnnAssign — silent skips would let new SKUs (e.g. `Field("pro_lifetime")`,
    `auto()`, computed values) drop without anyone noticing.
    """
    source = schema_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "PlanId":
            continue

        plan_ids: list[str] = []
        for item in node.body:
            # Skip docstrings (any expression statement) and `pass` placeholders.
            if isinstance(item, ast.Expr):
                continue
            if isinstance(item, ast.Pass):
                continue
            # Skip helper methods / nested classes — Enum subclasses can have
            # @classmethod, @property, etc. without those being plan SKUs.
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue

            target_name: str | None = None
            literal_value: str | None = None

            # Plain `pro_monthly = "pro_monthly"`
            if (
                isinstance(item, ast.Assign)
                and len(item.targets) == 1
                and isinstance(item.targets[0], ast.Name)
            ):
                target_name = item.targets[0].id
                literal_value = _extract_string_literal(item.value)

            # Annotated form `pro_monthly: str = "pro_monthly"` or
            # `pro_monthly: str = Field("pro_monthly", description="...")`
            elif (
                isinstance(item, ast.AnnAssign)
                and isinstance(item.target, ast.Name)
            ):
                target_name = item.target.id
                if item.value is not None:
                    literal_value = _extract_string_literal(item.value)

            # Skip Enum housekeeping members (`_ignore_`, `__order__`, etc.) —
            # they're not plan SKUs and must not leak into the FE list.
            if target_name is not None and (
                target_name.startswith("_") or target_name.startswith("__")
            ):
                continue

            # Real member but in a shape we don't recognize → fail loud.
            # Better to break codegen than to silently drop a real plan.
            if target_name is None or literal_value is None:
                raise RuntimeError(
                    f"PlanId enum has an unexpected member shape at "
                    f"{schema_path}:{getattr(item, 'lineno', '?')}: "
                    f"{ast.dump(item)}.\n"
                    f"generate_plan_ids.py supports plain string literals or "
                    f"`Field(\"value\", ...)`-style calls. Update this script "
                    f"if BE uses a new pattern."
                )

            plan_ids.append(literal_value)

        if not plan_ids:
            raise RuntimeError(f"PlanId class found but no string members in {schema_path}")
        return plan_ids

    raise RuntimeError(f"PlanId class not found in {schema_path}")


def render_ts(plan_ids: list[str]) -> str:
    """Render TypeScript output preserving the BE declaration order."""
    quoted = ", ".join(f'"{p}"' for p in plan_ids)
    return (
        "// AUTO-GENERATED from nowing_backend/app/schemas/stripe.py:PlanId\n"
        "// DO NOT EDIT — regenerate via `pnpm gen:plan-ids` (or python3 scripts/generate_plan_ids.py)\n"
        "// CI drift check: pnpm verify:plan-ids\n"
        "// Reference: ADR-012 (Entitlement Plan IDs Single Source of Truth)\n"
        "\n"
        f"export const PRO_PLANS = [{quoted}] as const;\n"
        "\n"
        "export type ProPlan = (typeof PRO_PLANS)[number];\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if generated file differs from committed version",
    )
    args = parser.parse_args()

    plan_ids = extract_plan_ids(BE_SCHEMA)
    rendered = render_ts(plan_ids)

    FE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    if args.check:
        if not FE_OUTPUT.exists():
            print(
                f"DRIFT: {FE_OUTPUT} does not exist. Run "
                f"`python3 scripts/generate_plan_ids.py` to create it.",
                file=sys.stderr,
            )
            return 1
        committed = FE_OUTPUT.read_text(encoding="utf-8")
        if committed != rendered:
            print(
                f"DRIFT: {FE_OUTPUT} is out of sync with BE PlanId enum.\n"
                f"Run `python3 scripts/generate_plan_ids.py` and commit the result.",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {FE_OUTPUT.relative_to(REPO_ROOT)} matches BE PlanId enum.")
        return 0

    FE_OUTPUT.write_text(rendered, encoding="utf-8")
    print(
        f"Wrote {FE_OUTPUT.relative_to(REPO_ROOT)} "
        f"({len(plan_ids)} plan{'s' if len(plan_ids) != 1 else ''}: {sorted(plan_ids)})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
