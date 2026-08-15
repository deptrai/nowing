"""SERP Dork Query Builder for LinkedIn Executive Search (Story 21.9 / AD-LI-4)."""

from __future__ import annotations

import re

from app.proprietary.platforms.linkedin.schemas import DEFAULT_EXECUTIVE_ROLES


def _sanitize_company_name(name: str) -> str:
    """Sanitize company name by removing unescaped quotes and extra whitespace."""
    if not name:
        return ""
    # Strip inner quotes to avoid broken SERP queries
    cleaned = re.sub(r'["\r\n\t]+', " ", name).strip()
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
    clean_company = _sanitize_company_name(company_name)
    if not clean_company:
        raise ValueError("Company name must not be empty.")

    target_roles = [r.strip() for r in (roles or DEFAULT_EXECUTIVE_ROLES) if r and r.strip()]
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
