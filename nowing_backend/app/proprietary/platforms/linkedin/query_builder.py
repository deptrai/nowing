"""SERP Dork Query Builder for LinkedIn Executive Search (Story 21.9 / AD-LI-4)."""

from __future__ import annotations

import re

from app.proprietary.platforms.linkedin.schemas import DEFAULT_EXECUTIVE_ROLES


def _sanitize_term(term: str) -> str:
    """Sanitize a search term by stripping quotes, parenthesis, and extra whitespace."""
    if not term:
        return ""
    cleaned = re.sub(r'["\(\)\r\n\t]+', " ", term).strip()
    return " ".join(cleaned.split())


def build_serp_dork_query(
    company_name: str,
    roles: list[str] | None = None,
    domain: str | None = None,
) -> str:
    """Construct privacy-compliant Google/Bing SERP dork query for LinkedIn profiles.

    Example output:
        site:linkedin.com/in/ "Vingroup" ("CEO" OR "Founder" OR "HR Director" OR "CTO")
    """
    clean_company = _sanitize_term(company_name)
    if not clean_company:
        raise ValueError("Company name must not be empty.")

    raw_roles = roles or DEFAULT_EXECUTIVE_ROLES
    target_roles = [_sanitize_term(r) for r in raw_roles if r and _sanitize_term(r)]
    if not target_roles:
        target_roles = ["CEO", "Founder", "Director"]

    # Role terms enclosed in double quotes joined by OR
    role_terms = " OR ".join(f'"{r}"' for r in target_roles)

    query_parts = [
        "site:linkedin.com/in/",
        f'"{clean_company}"',
        f"({role_terms})",
    ]

    return " ".join(query_parts)

