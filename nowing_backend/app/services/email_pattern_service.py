"""B2B Corporate Email Prediction & DNS MX Verifier (Story 21.9 / AD-LI-7)."""

from __future__ import annotations

import functools
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

# Prefixes and titles to strip from names before email generation
_PREFIXES_REGEX = re.compile(
    r"^(?:(?:mr|mrs|ms|dr|prof|ts|ths|pgs|gs)\.?|ông|bà|anh|chị)\s+",
    re.IGNORECASE,
)

# Professional suffixes / degrees to strip (e.g. "Nguyen Van A, CFA, MBA")
_SUFFIXES_REGEX = re.compile(
    r"(?:,\s*|\s+)(?:phd|mba|cfa|pmp|acca|cpa|esq|md|bsc|msc|llm|jd)\b.*$",
    re.IGNORECASE,
)

_VIETNAMESE_SURNAMES = {
    "nguyen", "tran", "le", "pham", "hoang", "huynh", "phan", "vu", "vo",
    "dang", "bui", "do", "ho", "ngo", "duong", "ly", "dinh", "doan",
    "lam", "trinh", "mai", "dao", "cao", "ha", "luong", "thai", "chau",
    "ta", "phung", "quan", "ton", "trieu", "nghiem", "luc", "khuong",
}


def _strip_accents_and_normalize(text: str) -> str:
    """Strip Vietnamese and Unicode diacritics into plain ASCII."""
    if not text:
        return ""
    # Explicitly handle Vietnamese 'đ' / 'Đ'
    text = text.replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFD", text)
    ascii_bytes = normalized.encode("ascii", "ignore")
    return ascii_bytes.decode("utf-8").strip()


def normalize_name_for_email(name: str) -> tuple[str, str, str]:
    """Normalize full name into (first_name, last_name, clean_full_name).

    Handles both Vietnamese and Western name conventions:
    - Vietnamese: "Nguyễn Văn An" -> first="an", last="nguyen", full="nguyen van an"
    - Western: "John Doe" -> first="john", last="doe", full="john doe"
    - Western + VN Surname: "David Nguyen" -> first="david", last="nguyen", full="david nguyen"
    """
    if not name:
        return ("", "", "")

    # Strip suffixes / professional degrees
    cleaned = _SUFFIXES_REGEX.sub("", name.strip())
    # Strip multiple/nested prefixes
    prev = None
    while prev != cleaned:
        prev = cleaned
        cleaned = _PREFIXES_REGEX.sub("", cleaned.strip())

    # Strip diacritics
    ascii_clean = _strip_accents_and_normalize(cleaned)
    # Remove non-alpha characters except spaces and hyphens
    sanitized = re.sub(r"[^a-zA-Z\s-]", "", ascii_clean).lower()
    tokens = [t.strip() for t in sanitized.split() if t.strip()]

    if not tokens:
        return ("", "", "")
    if len(tokens) == 1:
        return (tokens[0], tokens[0], tokens[0])

    if len(tokens) == 2:
        # If tokens[0] is a VN surname and tokens[1] is not, it's VN order [Họ Tên]
        # (e.g. "Nguyen An" -> first="an", last="nguyen")
        if tokens[0] in _VIETNAMESE_SURNAMES and tokens[1] not in _VIETNAMESE_SURNAMES:
            first_token = tokens[1]
            last_token = tokens[0]
        else:
            # Western order [Given Family] (e.g. "John Doe", "David Nguyen")
            first_token = tokens[0]
            last_token = tokens[1]
    else:
        # 3+ tokens: check if first token is a VN surname
        if tokens[0] in _VIETNAMESE_SURNAMES:
            first_token = tokens[-1]  # Given name
            last_token = tokens[0]   # Family name
        else:
            first_token = tokens[0]
            last_token = tokens[-1]

    full_clean = " ".join(tokens)
    return (first_token, last_token, full_clean)


def generate_email_candidates(full_name: str, domain: str) -> list[str]:
    """Generate canonical B2B corporate email patterns for a person and domain."""
    if not full_name or not domain:
        return []

    # Clean domain (strip http/https, www, trailing slashes, and invalid chars)
    clean_domain = domain.lower().strip()
    clean_domain = re.sub(r"^https?://", "", clean_domain)
    clean_domain = re.sub(r"^www\.", "", clean_domain)
    clean_domain = clean_domain.split("/")[0].split(":")[0].split("@")[-1].strip()

    if not clean_domain or "." not in clean_domain:
        return []

    first, last, full = normalize_name_for_email(full_name)
    if not first or not last:
        return [f"info@{clean_domain}", f"contact@{clean_domain}"]

    tokens = full.split()
    if len(tokens) == 1:
        return [f"{first}@{clean_domain}", f"contact@{clean_domain}", f"info@{clean_domain}"]

    f_init = first[0] if first else ""

    patterns: list[str] = []

    # Pattern 1: first.last@domain (e.g. an.nguyen@company.com / john.doe@company.com)
    patterns.append(f"{first}.{last}@{clean_domain}")

    # Pattern 2: last.first@domain (e.g. nguyen.an@company.com)
    patterns.append(f"{last}.{first}@{clean_domain}")

    # Pattern 3: first@domain (e.g. an@company.com / john@company.com)
    patterns.append(f"{first}@{clean_domain}")

    # Pattern 4: last@domain (e.g. nguyen@company.com)
    patterns.append(f"{last}@{clean_domain}")

    # Pattern 5: first_initial.last@domain (e.g. a.nguyen@company.com / j.doe@company.com)
    patterns.append(f"{f_init}.{last}@{clean_domain}")

    # Pattern 6: first_initial_last@domain (e.g. jdoe@company.com)
    patterns.append(f"{f_init}{last}@{clean_domain}")

    # Pattern 7: last.first_initial@domain (e.g. nguyen.a@company.com)
    patterns.append(f"{last}.{f_init}@{clean_domain}")

    # Pattern 8: firstlast@domain (e.g. annguyen@company.com)
    patterns.append(f"{first}{last}@{clean_domain}")

    # Pattern 9: lastfirst@domain (e.g. nguyenan@company.com)
    patterns.append(f"{last}{first}@{clean_domain}")

    # Pattern 10: first_last@domain (e.g. an_nguyen@company.com)
    patterns.append(f"{first}_{last}@{clean_domain}")

    # If full name has 3+ parts: e.g. "Nguyen Van An" -> "nguyenva@domain"
    if len(tokens) >= 3:
        initials_middle = "".join(t[0] for t in tokens[1:-1])
        patterns.append(f"{last}{initials_middle}{f_init}@{clean_domain}")
        patterns.append(f"{first}.{tokens[1]}@{clean_domain}")

    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            deduped.append(p)

    return deduped


@functools.lru_cache(maxsize=1024)
def check_domain_mx(domain: str, timeout: float = 3.0) -> bool:
    """Verify if a domain has valid DNS MX records with LRU cache and timeout safety."""
    if not domain:
        return False

    clean_domain = domain.lower().strip()
    clean_domain = re.sub(r"^https?://", "", clean_domain)
    clean_domain = re.sub(r"^www\.", "", clean_domain)
    clean_domain = clean_domain.split("/")[0].split(":")[0].split("@")[-1].strip()

    if not clean_domain or "." not in clean_domain:
        return False

    try:
        import dns.resolver

        resolver = dns.resolver.Resolver()
        resolver.lifetime = timeout
        resolver.timeout = timeout
        answers = resolver.resolve(clean_domain, "MX")
        return bool(answers and len(answers) > 0)
    except Exception as e:
        logger.debug(f"DNS MX resolution failed for domain '{clean_domain}': {e}")
        return False


def predict_executive_email(
    full_name: str,
    domain: str,
    check_mx: bool = True,
    mx_override: bool | None = None,
) -> tuple[str | None, list[str], float, bool]:
    """Predict corporate emails and return (best_email, all_candidates, confidence, mx_valid).

    Confidence Score Rules:
    - If MX valid: top candidate confidence = 0.85
    - If MX check disabled / unknown: confidence = 0.60
    - If MX invalid: confidence = 0.40
    """
    candidates = generate_email_candidates(full_name, domain)
    if not candidates:
        return (None, [], 0.0, False)

    if mx_override is not None:
        mx_valid = mx_override
        confidence = 0.85 if mx_valid else 0.40
    elif check_mx and domain:
        mx_valid = check_domain_mx(domain)
        confidence = 0.85 if mx_valid else 0.40
    else:
        mx_valid = False
        confidence = 0.60

    best_email = candidates[0] if candidates else None
    return (best_email, candidates, confidence, mx_valid)
