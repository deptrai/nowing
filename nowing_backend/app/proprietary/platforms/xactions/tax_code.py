"""Vietnamese Tax Code (Mã số thuế - MST) Modulo-11 validator and extractor."""

from __future__ import annotations

import re
import time

from app.proprietary.platforms.xactions.phone_extractor import _VN_PHONE_REGEX

# Weight coefficients for the 9 leading digits of a 10-digit Vietnamese tax code
_WEIGHTS = [31, 29, 23, 19, 17, 13, 7, 5, 3]

# Main 10-digit MST group with optional [.\s-] delimiters (e.g. 0100.109.106 or O1OO1O91O6)
_TAX_MAIN_GROUP = r"[0-9oO]{4}(?:[.\s-]?[0-9oO]{3}){2}"

# Optional 3-digit branch suffix, also allowing a leading delimiter
_TAX_BRANCH_GROUP = r"(?:[.\s-]?(?P<branch>[0-9oO]{3}))"


_TAX_KEYWORDS = (
    r"MST|Mã\s*số\s*thuế|Mã\s*số\s*DN|MSDN|Mã\s*số\s*doanh\s*nghiệp|Tax\s*ID|Tax\s*code"
)

_KEYWORD_TAX_PATTERN = re.compile(
    r"(?i:\b(?:"
    + _TAX_KEYWORDS
    + r")[^0-9oO\n]{0,30}?)(?P<main>"
    + _TAX_MAIN_GROUP
    + r")"
    + _TAX_BRANCH_GROUP
    + r"?\b"
)

_STANDALONE_TAX_PATTERN = re.compile(
    r"\b(?P<main>\d{4}(?:[.\s-]?\d{3}){2})" + r"(?:[.\s-]?(?P<branch>\d{3}))?" + r"\b"
)


def is_valid_vietnam_tax_code(tax_id: str | None) -> bool:
    """Validate a Vietnamese tax code (10-digit enterprise MST or 13-digit branch MST).

    Implements the Modulo-11 checksum according to Circular 05/2017/TT-BTC & 105/2020/TT-BTC:
    Sum = d1*31 + d2*29 + d3*23 + d4*19 + d5*17 + d6*13 + d7*7 + d8*5 + d9*3
    Check digit d10 = 10 - (Sum % 11). (If 10 - (Sum % 11) == 10, d10 is 0).
    For 13-digit branch codes, the first 10 digits must pass the check and the last 3 digits
    must be numeric.
    """
    if not tax_id or not isinstance(tax_id, str):
        return False

    # Normalize letter o/O to 0, and strip non-digit characters
    normalized = re.sub(r"[oO]", "0", tax_id)
    cleaned = re.sub(r"[^\d]", "", normalized)

    if len(cleaned) not in (10, 13):
        return False

    digits = [int(c) for c in cleaned[:10]]
    checksum = sum(d * w for d, w in zip(digits[:9], _WEIGHTS, strict=True))
    remainder = checksum % 11
    expected_check_digit = 10 - remainder
    if expected_check_digit == 10:
        expected_check_digit = 0

    return digits[9] == expected_check_digit


def _clean_match(value: str | None) -> str:
    """Normalize and remove any non-digit characters from a matched group."""
    if not value:
        return ""
    normalized = re.sub(r"[oO]", "0", value)
    return re.sub(r"[^\d]", "", normalized)


def _is_phone_like(digits: str) -> bool:
    """Return True if a 10-digit number matches the Vietnamese mobile phone pattern."""
    return bool(_VN_PHONE_REGEX.fullmatch(digits))


def extract_tax_ids(
    text: str | None,
    timeout_sec: float = 5.0,
    max_length: int = 200_000,
) -> list[str]:
    """Extract candidate 10-digit or 13-digit tax codes from unstructured text.

    Extracts numbers explicitly preceded by tax keywords (MST, Mã số thuế, etc.),
    as well as standalone 10/13 digit numbers that satisfy the Modulo-11 algorithm.
    Numbers that look like Vietnamese mobile phones are excluded from the standalone
    matcher to avoid phone false-positives.

    A per-call CPU-time timeout and a hard input-length cap protect against ReDoS or
    adversarial payloads.
    """
    if not text or not isinstance(text, str):
        return []

    if len(text) > max_length:
        text = text[:max_length]

    deadline = time.perf_counter() + timeout_sec
    seen: set[str] = set()
    results: list[str] = []

    def _add(
        main: str,
        branch: str | None,
        *,
        require_valid: bool = True,
        allow_phone_like: bool = False,
    ) -> None:
        main_digits = _clean_match(main)
        if len(main_digits) != 10:
            return
        if not allow_phone_like and _is_phone_like(main_digits):
            return
        branch_digits = _clean_match(branch) if branch else ""
        candidate = f"{main_digits}-{branch_digits}" if branch_digits else main_digits
        if candidate in seen:
            return
        if require_valid and not is_valid_vietnam_tax_code(candidate):
            return
        seen.add(candidate)
        results.append(candidate)

    # 1. First extract candidates explicitly preceded by tax code keywords.
    #    Keyword context is trusted enough to include even invalid MSTs (so the
    #    caller can flag them), but phone-pattern numbers are still excluded.
    for match in _KEYWORD_TAX_PATTERN.finditer(text):
        if time.perf_counter() > deadline:
            break
        _add(match.group("main"), match.group("branch"), require_valid=False)

    # 2. Extract standalone 10/13 digit groups only if they pass Modulo-11 and are
    #    not phone-like, reducing false positives from bank accounts or order IDs.
    if time.perf_counter() <= deadline:
        for match in _STANDALONE_TAX_PATTERN.finditer(text):
            if time.perf_counter() > deadline:
                break
            _add(match.group("main"), match.group("branch"), require_valid=True)

    return results
