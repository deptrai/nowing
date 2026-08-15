"""SERP HTML Parser for LinkedIn Leadership Profiles (Story 21.9 / AD-LI-4)."""

from __future__ import annotations

import logging
import re
from urllib.parse import unquote

from selectolax.parser import HTMLParser

from app.proprietary.platforms.linkedin.schemas import ExecutiveProfile
from app.services.email_pattern_service import predict_executive_email

logger = logging.getLogger(__name__)

_LINKEDIN_SLUG_REGEX = re.compile(
    r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/([^/?#\s]+)",
    re.IGNORECASE,
)


def parse_linkedin_slug(url_or_text: str) -> str | None:
    """Extract clean LinkedIn slug from a public LinkedIn profile URL."""
    if not url_or_text:
        return None
    match = _LINKEDIN_SLUG_REGEX.search(url_or_text.strip())
    if not match:
        return None
    slug = match.group(1).rstrip("/")
    decoded = unquote(slug).strip()
    return decoded if decoded else None


def parse_serp_title_and_snippet(
    title: str,
    snippet: str,
    target_company: str | None = None,
) -> tuple[str, str | None, str | None]:
    """Parse Google/Bing SERP title into (full_name, title, company_name).

    Examples:
        - "Nguyen Van A - Chief Executive Officer - FPT Software | LinkedIn"
          -> ("Nguyen Van A", "Chief Executive Officer", "FPT Software")
        - "Jane Doe - HR Director at TechCorp | LinkedIn"
          -> ("Jane Doe", "HR Director", "TechCorp")
    """
    if not title:
        return ("Unknown", None, target_company)

    # Remove trailing "| LinkedIn" or "- LinkedIn"
    cleaned_title = re.sub(r"[\s\|\-]+LinkedIn.*$", "", title, flags=re.IGNORECASE).strip()

    # Split by common delimiters: hyphen, en-dash, em-dash
    parts = re.split(r"\s+[-\u2013\u2014]\s+", cleaned_title)

    if len(parts) >= 3:
        full_name = parts[0].strip()
        role = parts[1].strip()
        comp = parts[2].strip()
        return (full_name, role, comp or target_company)

    if len(parts) == 2:
        full_name = parts[0].strip()
        second_part = parts[1].strip()
        # Check if second part contains "at Company"
        if " at " in second_part:
            role_part, comp_part = second_part.split(" at ", 1)
            return (full_name, role_part.strip(), comp_part.strip() or target_company)
        return (full_name, second_part, target_company)

    # Single token title: fallback
    return (cleaned_title, None, target_company)


class ExecutiveParser:
    """Selectolax-based fast parser for SERP pages."""

    def parse_serp_html(
        self,
        html_content: str,
        target_company: str,
        domain: str | None = None,
    ) -> list[ExecutiveProfile]:
        """Extract structured ExecutiveProfile instances from SERP HTML."""
        if not html_content:
            return []

        tree = HTMLParser(html_content)
        profiles: list[ExecutiveProfile] = []
        seen_slugs: set[str] = set()

        # Find all anchor tags that link to linkedin.com/in/
        anchors = tree.css("a[href*='linkedin.com/in/']")

        for a in anchors:
            href = a.attributes.get("href", "")
            slug = parse_linkedin_slug(href)
            if not slug or slug in seen_slugs:
                continue

            # Title extraction: from <h3> or text inside anchor
            h3_node = a.css_first("h3")
            title_text = h3_node.text().strip() if h3_node else a.text().strip()

            # Snippet extraction: try sibling or ancestor container text
            snippet_text = ""
            parent = a.parent
            for _ in range(4):
                if not parent:
                    break
                snippet_node = parent.css_first(".VwiC3b, .snippet, .b_caption p, .result__snippet")
                if snippet_node:
                    snippet_text = snippet_node.text().strip()
                    break
                parent = parent.parent

            full_name, role, extracted_comp = parse_serp_title_and_snippet(
                title_text,
                snippet_text,
                target_company=target_company,
            )

            # Inferred emails & MX check
            best_email, candidates, confidence, mx_valid = predict_executive_email(
                full_name=full_name,
                domain=domain or "",
                check_mx=bool(domain),
            )

            profile = ExecutiveProfile(
                full_name=full_name,
                title=role or "Executive",
                company_name=extracted_comp or target_company,
                linkedin_url=f"https://vn.linkedin.com/in/{slug}",
                linkedin_slug=slug,
                department="Executive Leadership",
                inferred_emails=candidates,
                email_prediction=best_email,
                confidence_score=confidence,
                verified_mx=mx_valid,
                source_query=f'site:linkedin.com/in/ "{target_company}"',
                raw_metadata={"serp_title": title_text, "snippet": snippet_text},
            )

            seen_slugs.add(slug)
            profiles.append(profile)

        return profiles
