"""Fast, multi-layer Anti-SSRF Crawler & Metadata Extractor (Story 21.10 / AC 1, 2, 3)."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
import socket
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import httpx
from selectolax.parser import HTMLParser

logger = logging.getLogger(__name__)

# RFC 1918, Loopback, Link-Local, Cloud Metadata & Carrier-grade NAT subnets
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local & AWS/GCP Metadata 169.254.169.254
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-grade NAT
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),  # TEST-NET-1
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),  # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved
    ipaddress.ip_network("::1/128"),  # IPv6 Loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 Unique Local
    ipaddress.ip_network("fe80::/10"),  # IPv6 Link-Local
]

_TRACKING_PARAM_PREFIXES = ("utm_", "fbclid", "gclid", "ref", "ref_", "source", "campaign", "mc_eid")
_MAX_REDIRECT_HOPS = 3
_MAX_BODY_TEXT_CHARS = 2000


class SSRFProtectionError(ValueError):
    """Raised when a URL targets private, loopback, or restricted subnets."""


class FastCrawlerTimeoutError(TimeoutError):
    """Raised when crawling or connecting to a target website times out."""


@dataclass
class CrawlMetadata:
    url: str
    final_url: str
    status_code: int
    title: str = ""
    description: str = ""
    keywords: str = ""
    og_tags: dict[str, str] = field(default_factory=dict)
    json_ld: list[dict[str, Any]] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    clean_text: str = ""
    latency_ms: float = 0.0


def normalize_target_url(raw_url: str) -> str:
    """Normalize input URL by adding https:// scheme, stripping tracking params and trailing slashes."""
    if not raw_url or not isinstance(raw_url, str):
        raise ValueError("URL must be a non-empty string")

    s = raw_url.strip()
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", s):
        s = f"https://{s}"

    parsed = urlparse(s)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {scheme}. Only http and https are allowed.")

    netloc = parsed.netloc.strip().lower()
    if not netloc:
        raise ValueError("Invalid URL: missing host")

    # Strip port if standard
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    # Filter out tracking query parameters
    query_params = parse_qs(parsed.query, keep_blank_values=False)
    filtered_params = {
        k: v
        for k, v in query_params.items()
        if not any(k.lower().startswith(prefix) for prefix in _TRACKING_PARAM_PREFIXES)
    }
    new_query = urlencode(filtered_params, doseq=True)

    path = parsed.path.rstrip("/")

    return urlunparse((scheme, netloc, path, "", new_query, ""))


async def validate_safe_ip(hostname: str) -> bool:
    """Resolve DNS asynchronously and verify that no resolved IP is in restricted subnets.

    Returns True if all resolved IPs are safe and public, False otherwise.
    """
    if not hostname:
        return False

    # Check localhost string
    if hostname.lower() in ("localhost", "localhost.localdomain", "broadcasthost"):
        return False

    loop = asyncio.get_event_loop()
    try:
        addr_info = await loop.getaddrinfo(
            hostname,
            None,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except (socket.gaierror, Exception):
        return False

    if not addr_info:
        return False

    for entry in addr_info:
        sockaddr = entry[4]
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            return False

        for blocked in _BLOCKED_NETWORKS:
            if ip_obj in blocked:
                return False

    return True


def _flatten_json_ld_item(item: Any, target_types: set[str]) -> list[dict[str, Any]]:
    """Recursively extract schemas from JSON-LD, flattening @graph arrays."""
    results = []
    if isinstance(item, list):
        for sub in item:
            results.extend(_flatten_json_ld_item(sub, target_types))
        return results

    if isinstance(item, dict):
        if "@graph" in item and isinstance(item["@graph"], list):
            for sub in item["@graph"]:
                results.extend(_flatten_json_ld_item(sub, target_types))
            return results

        schema_type = item.get("@type")
        if isinstance(schema_type, list):
            if any(t in target_types for t in schema_type):
                results.append(item)
        elif isinstance(schema_type, str) and (
            schema_type in target_types or any(t.lower() in schema_type.lower() for t in target_types)
        ):
            results.append(item)
    return results


def extract_json_ld_metadata(tree: HTMLParser) -> list[dict[str, Any]]:
    """Extract Schema.org JSON-LD scripts with recursive @graph flattening."""
    target_types = {
        "RealEstateListing",
        "Product",
        "Organization",
        "LocalBusiness",
        "Service",
        "WebSite",
        "WebPage",
        "Corporation",
    }
    extracted = []
    for node in tree.css('script[type="application/ld+json"]'):
        text = node.text()
        if not text:
            continue
        try:
            parsed = json.loads(text.strip())
            extracted.extend(_flatten_json_ld_item(parsed, target_types))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return extracted


class FastCrawler:
    """Fast, SSRF-safe HTTP Crawler with HTML and Schema metadata extraction."""

    def __init__(self, user_agent: str | None = None):
        self.user_agent = (
            user_agent
            or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Nowing/1.0"
        )
        self.timeout = httpx.Timeout(connect=1.5, read=2.0, write=1.5, pool=2.0)

    def extract_opengraph(self, tree: HTMLParser) -> dict[str, str]:
        """Extract OpenGraph meta tags."""
        og_tags: dict[str, str] = {}
        for node in tree.css('meta[property^="og:"], meta[name^="og:"]'):
            prop = node.attributes.get("property") or node.attributes.get("name")
            content = node.attributes.get("content")
            if prop and content:
                og_tags[prop.strip()] = content.strip()
        return og_tags

    def extract_clean_hero_text(self, tree: HTMLParser, max_chars: int = 2000) -> str:
        """Extract clean body text stripped of boilerplate nav/footer/script."""
        for unwanted in tree.css("script, style, nav, footer, header, aside, noscript, svg, button, form, iframe"):
            unwanted.decompose()

        main_node = tree.css_first("main, article, #content, .content, body")
        raw_clean_text = main_node.text(separator=" ", strip=True) if main_node else tree.text(separator=" ", strip=True)
        clean_text = re.sub(r"\s+", " ", raw_clean_text).strip()
        if len(clean_text) > max_chars:
            clean_text = clean_text[:max_chars]
        return clean_text

    async def _send_raw_request(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        """Execute raw GET request using client with timeout handling."""
        try:
            return await client.get(url)
        except httpx.TimeoutException as exc:
            raise FastCrawlerTimeoutError(f"Crawl connection timed out fetching {url}: {exc}") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"HTTP request error fetching {url}: {exc}") from exc

    async def fetch_and_parse(self, raw_url: str) -> CrawlMetadata:
        """Fetch URL with SSRF checks on every hop, then extract metadata within latency budget."""
        start_time = time.monotonic()
        normalized_url = normalize_target_url(raw_url)

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Ch-Ua": '"Not)A;Brand";v="99", "Google Chrome";v="127"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
        }

        current_url = normalized_url
        response = None

        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=self.timeout,
            headers=headers,
            verify=True,
        ) as client:
            for _ in range(_MAX_REDIRECT_HOPS + 1):
                parsed = urlparse(current_url)
                if not await validate_safe_ip(parsed.hostname or ""):
                    raise SSRFProtectionError(
                        f"Target hostname '{parsed.hostname}' resolves to blocked private/reserved IP or invalid address"
                    )

                response = await self._send_raw_request(client, current_url)

                if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location:
                        break
                    current_url = urljoin(current_url, location)
                    current_url = normalize_target_url(current_url)
                    continue

                break

        if response is None:
            raise RuntimeError("No HTTP response received")

        html_text = response.text
        tree = HTMLParser(html_text)

        # 1. OpenGraph tags
        og_tags = self.extract_opengraph(tree)

        # 2. Title & Meta description/keywords
        title_node = tree.css_first("title")
        title = title_node.text().strip() if title_node else og_tags.get("og:title", "")

        desc_node = tree.css_first('meta[name="description"]')
        description = (
            desc_node.attributes.get("content", "").strip()
            if desc_node
            else og_tags.get("og:description", "")
        )

        kw_node = tree.css_first('meta[name="keywords"]')
        keywords = kw_node.attributes.get("content", "").strip() if kw_node else ""

        # 3. Schema.org JSON-LD
        json_ld = extract_json_ld_metadata(tree)

        # 4. Headings h1, h2, h3 (first 5)
        headings: list[str] = []
        for h_node in tree.css("h1, h2, h3"):
            h_text = h_node.text(strip=True)
            if h_text and len(h_text) > 3:
                headings.append(h_text)
            if len(headings) >= 5:
                break

        # 5. Clean body text stripped of boilerplate
        clean_text = self.extract_clean_hero_text(tree, _MAX_BODY_TEXT_CHARS)

        latency_ms = (time.monotonic() - start_time) * 1000.0

        return CrawlMetadata(
            url=normalized_url,
            final_url=current_url,
            status_code=response.status_code,
            title=title,
            description=description,
            keywords=keywords,
            og_tags=og_tags,
            json_ld=json_ld,
            headings=headings,
            clean_text=clean_text,
            latency_ms=latency_ms,
        )
