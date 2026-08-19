#!/usr/bin/env python3
"""Pre-commit / CI check that lead-extraction cassettes are sanitized.

For every cassette supplied on the command line, verify that the recorded
``phones``, ``tax_ids``, and ``company_name`` values match the expected values
in ``data/lead_extraction/regression/cases.jsonl``. Any cassette that contains
PII not present in the committed, sanitized cases is rejected.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CASES_FILE = _PROJECT_ROOT / "nowing_evals" / "data" / "lead_extraction" / "regression" / "cases.jsonl"


def _load_cases() -> dict[str, dict[str, object]]:
    cases: dict[str, dict[str, object]] = {}
    if not _CASES_FILE.is_file():
        return cases
    for line in _CASES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Malformed cases.jsonl: {exc}") from exc
        case_id = case.get("case_id")
        if isinstance(case_id, str):
            cases[case_id] = case
    return cases


def _norm(value: str) -> str:
    return re.sub(r"[^\d]", "", value)


def _check_cassette(path: Path, cases: dict[str, dict[str, object]]) -> list[str]:
    errors: list[str] = []
    m = re.fullmatch(r"([a-zA-Z0-9_-]+)\.sse\.jsonl", path.name)
    if not m:
        errors.append(f"{path}: filename must be <case_id>.sse.jsonl")
        return errors
    case_id = m.group(1)
    case = cases.get(case_id)
    if not case:
        errors.append(f"{path}: no matching case in cases.jsonl")
        return errors

    try:
        data = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: invalid JSON ({exc})")
        return errors

    if not isinstance(data, dict) or not isinstance(data.get("body"), dict):
        errors.append(f"{path}: cassette must be a JSON object with a dict 'body'")
        return errors

    body = data["body"]
    allowed_phones = {str(p) for p in (case.get("expected_phones") or [])}
    allowed_tax = {_norm(str(t)) for t in (case.get("expected_tax_ids") or [])}
    allowed_company = {case.get("expected_company_name")}

    for phone in body.get("phones") or []:
        if str(phone) not in allowed_phones:
            errors.append(
                f"{path}: unsanitized or unexpected phone {phone!r} "
                f"(allowed: {sorted(allowed_phones)})"
            )

    for tax in body.get("tax_ids") or []:
        if _norm(str(tax)) not in allowed_tax:
            errors.append(
                f"{path}: unsanitized or unexpected tax_id {tax!r} "
                f"(allowed: {sorted(allowed_tax)})"
            )

    company = body.get("company_name")
    if company is not None and company not in allowed_company:
        errors.append(
            f"{path}: unsanitized or unexpected company_name {company!r} "
            f"(allowed: {sorted(str(c) for c in allowed_company if c is not None)})"
        )

    return errors


def main(argv: list[str] | None = None) -> int:
    paths = argv or sys.argv[1:]
    if not paths:
        # Check all cassettes in the data dir.
        cassette_dir = _CASES_FILE.parent / "cassettes"
        if cassette_dir.is_dir():
            paths = [str(p) for p in sorted(cassette_dir.glob("*.sse.jsonl"))]
        else:
            paths = []

    cases = _load_cases()
    all_errors: list[str] = []
    for p in paths:
        all_errors.extend(_check_cassette(Path(p), cases))

    if all_errors:
        for error in all_errors:
            print(error, file=sys.stderr)
        print(
            "Cassette sanitization check failed. Re-record with "
            "`--record --mode live` after updating the dataset, or sanitize the cassettes.",
            file=sys.stderr,
        )
        return 1

    print("Cassette sanitization check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
