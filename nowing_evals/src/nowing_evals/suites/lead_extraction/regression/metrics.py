"""Metrics for lead extraction regression benchmark (AC-1 / AD-107)."""

from __future__ import annotations

import re
import unicodedata

# Letter-to-digit substitutions used in obfuscated phone numbers.
_HOMOGLYPH_O_RE = re.compile(r"[oOóòỏõọôốồổỗộơớờởỡợ]")
_HOMOGLYPH_O_REPLACEMENT = "0"
_HOMOGLYPH_LI_RE = re.compile(r"[lLiI|]")
_HOMOGLYPH_LI_REPLACEMENT = "1"

_LEGACY_11_MAP = {
    "0162": "032",
    "0163": "033",
    "0164": "034",
    "0165": "035",
    "0166": "036",
    "0167": "037",
    "0168": "038",
    "0169": "039",
    "0120": "070",
    "0121": "079",
    "0122": "077",
    "0126": "076",
    "0128": "078",
    "0123": "083",
    "0124": "084",
    "0125": "085",
    "0127": "081",
    "0129": "082",
    "0186": "056",
    "0188": "058",
    "0199": "059",
}

# Phone-like digit clusters in source text. Mirrors the backend extractor's
# candidate-formation step: allow delimiters and obfuscated letters.
_PHONE_CLUSTER_RE = re.compile(
    r"(?<!\w)(?:\+?[\doOlLiI|]{1,4}[.\s\-_/:()*]*)?[\doOlLiI|]{2,4}"
    r"(?:[.\s\-_/:()*]*[\doOlLiI|]{2,4}){2,5}",
    re.IGNORECASE,
)


def _decode_phone_candidate(candidate: str) -> str:
    """Replace obfuscated letters in a phone candidate before normalization."""
    candidate = _HOMOGLYPH_O_RE.sub(_HOMOGLYPH_O_REPLACEMENT, candidate)
    return _HOMOGLYPH_LI_RE.sub(_HOMOGLYPH_LI_REPLACEMENT, candidate)


def _preprocess_digit_string(text: str | None) -> str:
    """Return a digit-only string of the source text for tax membership tests."""
    if not text or not isinstance(text, str):
        return ""
    return re.sub(r"[^\d]", "", text)


def _normalized_source_phones(source_text: str | None) -> set[str]:
    """Return the set of normalized Vietnamese phones present in the source text."""
    if not source_text or not isinstance(source_text, str):
        return set()

    phones: set[str] = set()
    for candidate in _PHONE_CLUSTER_RE.findall(source_text):
        candidate = _decode_phone_candidate(candidate)
        phone = normalize_vn_phone(candidate)
        if phone:
            phones.add(phone)
    return phones


def normalize_vn_phone(phone: str | None) -> str | None:
    """Normalize a Vietnamese phone number to a standard 10-digit format starting with 0."""
    if not phone or not isinstance(phone, str):
        return None

    digits = re.sub(r"[^\d+]", "", phone)
    if digits.startswith("+84"):
        digits = "0" + digits[3:]
    elif digits.startswith("84") and len(digits) in (11, 12):
        digits = "0" + digits[2:]

    # Convert 11-digit legacy prefix
    if len(digits) == 11 and digits.startswith("01"):
        prefix = digits[:4]
        if prefix in _LEGACY_11_MAP:
            digits = _LEGACY_11_MAP[prefix] + digits[4:]

    if len(digits) == 10 and digits.startswith("0"):
        return digits

    return None


def f1_phone(predicted: set[str] | list[str], expected: set[str] | list[str]) -> float:
    """Compute entity-level F1 score over normalized Vietnamese phone sets."""
    p_set = {normalize_vn_phone(p) for p in predicted if normalize_vn_phone(p)}
    e_set = {normalize_vn_phone(e) for e in expected if normalize_vn_phone(e)}

    if not p_set and not e_set:
        return 1.0
    if not p_set or not e_set:
        return 0.0

    tp = len(p_set & e_set)
    precision = tp / len(p_set)
    recall = tp / len(e_set)

    if precision + recall == 0:
        return 0.0

    return round(2 * (precision * recall) / (precision + recall), 4)


def _normalize_company_name(name: str | None) -> set[str]:
    """Return a normalized token set for a company name."""
    if not name or not isinstance(name, str):
        return set()

    # NFKC helps with mixed-width / composed Vietnamese characters.
    text = unicodedata.normalize("NFKC", name).lower()
    # Drop common punctuation and whitespace.
    text = re.sub(r"[^\w\s\u00c0-\u1fff]", " ", text)
    tokens = {t for t in text.split() if t}
    return tokens


def company_name_f1(predicted: str | None, expected: str | None) -> float:
    """Compute token-level F1 for company-name extraction."""
    p_tokens = _normalize_company_name(predicted)
    e_tokens = _normalize_company_name(expected)

    if not p_tokens and not e_tokens:
        return 1.0
    if not p_tokens or not e_tokens:
        return 0.0

    tp = len(p_tokens & e_tokens)
    precision = tp / len(p_tokens)
    recall = tp / len(e_tokens)

    if precision + recall == 0:
        return 0.0

    return round(2 * (precision * recall) / (precision + recall), 4)


def hallucination_rate(
    predicted_phones: set[str] | list[str],
    predicted_tax_ids: set[str] | list[str],
    source_text: str | None,
    expected_phones: set[str] | list[str],
    expected_tax_ids: set[str] | list[str],
) -> float:
    """Compute hallucination rate: fraction of predictions not found in source text or expected set."""
    p_phones = {normalize_vn_phone(p) for p in predicted_phones if normalize_vn_phone(p)}
    e_phones = {normalize_vn_phone(e) for e in expected_phones if normalize_vn_phone(e)}
    p_tax = {re.sub(r"[^\d]", "", t) for t in predicted_tax_ids if re.sub(r"[^\d]", "", t)}
    e_tax = {re.sub(r"[^\d]", "", t) for t in expected_tax_ids if re.sub(r"[^\d]", "", t)}

    source_phones = _normalized_source_phones(source_text)
    source_tax_digits = _preprocess_digit_string(source_text)

    total_predicted = len(p_phones) + len(p_tax)
    if total_predicted == 0:
        return 0.0

    hallucinated = 0

    for phone in p_phones:
        if phone not in e_phones and phone not in source_phones:
            hallucinated += 1

    for tax in p_tax:
        if tax not in e_tax and tax not in source_tax_digits:
            hallucinated += 1

    return round(hallucinated / total_predicted, 4)


def mst_modulo11_accuracy(tax_ids_valid: list[bool]) -> float:
    """Compute fraction of returned tax IDs that passed Modulo-11 validation."""
    if not tax_ids_valid:
        return 1.0
    return round(sum(tax_ids_valid) / len(tax_ids_valid), 4)
