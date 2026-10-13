#!/usr/bin/env python3
"""Synthetic DNS probe for custom domain verification (Story 27.1 / Item 29).

Periodically checks DNS TXT `_nowing-verify.<domain>` and CNAME ingress records
for customer and workspace custom domains across staging and production.
Detects when DNS verification records or CNAME ingress mappings are deleted,
misconfigured, or expired by DNS providers.

Usage examples:
    # Check one or more domains with default CNAME target
    uv run python scripts/dns_synthetic_probe.py --domains shop.example.com app.mybrand.vn

    # Check a domain with an explicit verification token
    uv run python scripts/dns_synthetic_probe.py --domain shop.example.com --token aB3d...

    # Check multiple domain:token pairs
    uv run python scripts/dns_synthetic_probe.py --pair "site1.com:tok1" --pair "site2.com:tok2"

    # Query active verified custom domains from the database
    uv run python scripts/dns_synthetic_probe.py --check-db

    # Output structured JSON for monitoring / Prometheus / Datadog probes
    uv run python scripts/dns_synthetic_probe.py --domains shop.example.com --json

Exit codes:
    0: All probed domains passed both TXT and CNAME verification.
    1: One or more domains failed (records missing, mismatched, or DNS error).
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import secrets
import sys
from dataclasses import asdict, dataclass
from typing import Any

# Add backend root to sys.path so app modules can be loaded when needed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_TXT_LABEL = "_nowing-verify"
DEFAULT_TXT_PREFIX = "nowing-verify="
DEFAULT_CNAME_TARGET = "cname-ingress.apps.nowing.net"
DEFAULT_DNS_TIMEOUT = 5.0
DEFAULT_MAX_CNAME_DEPTH = 5


@dataclass
class DnsProbeTarget:
    """A target domain to verify via synthetic DNS queries."""

    domain: str
    token: str | None = None
    app_id: str | None = None
    workspace_id: int | None = None


@dataclass
class DnsProbeResult:
    """Result of probing a single custom domain."""

    domain: str
    txt_host: str
    txt_status: str  # "ok", "missing", "mismatch", "invalid_length", "error"
    txt_detail: str
    cname_target: str
    cname_status: str  # "ok", "mismatch", "no_record", "error"
    cname_detail: str
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_dns_resolver(
    timeout: float = DEFAULT_DNS_TIMEOUT,
    nameserver: str | None = None,
) -> Any:
    """Create a configured dnspython resolver instance."""
    import dns.resolver

    resolver = dns.resolver.Resolver()
    resolver.lifetime = timeout
    resolver.timeout = timeout
    if nameserver:
        resolver.nameservers = [nameserver]
    return resolver


async def check_txt_ownership(
    domain: str,
    token: str | None = None,
    txt_label: str = DEFAULT_TXT_LABEL,
    txt_prefix: str = DEFAULT_TXT_PREFIX,
    timeout: float = DEFAULT_DNS_TIMEOUT,
    nameserver: str | None = None,
) -> tuple[str, str, str]:
    """Check TXT proof-of-ownership at ``<txt_label>.<domain>``.

    Returns:
        tuple of (status, detail, txt_host)
        status is one of: "ok", "missing", "mismatch", "invalid_length", "error"
    """
    import dns.resolver

    clean_domain = domain.lower().rstrip(".")
    txt_host = f"{txt_label}.{clean_domain}"

    # RFC 1035 caps DNS hostname at 253 octets.
    if len(txt_host) > 253:
        return (
            "invalid_length",
            f"Hostname exceeds 253 chars ({len(txt_host)})",
            txt_host,
        )

    resolver = get_dns_resolver(timeout=timeout, nameserver=nameserver)
    expected_full = f"{txt_prefix}{token}" if token else None

    try:
        answers = await asyncio.to_thread(resolver.resolve, txt_host, "TXT")
        found_values: list[str] = []
        for rdata in answers:
            if hasattr(rdata, "strings") and isinstance(rdata.strings, (list, tuple)):
                raw_str = b"".join(rdata.strings).decode("utf-8", errors="replace")
            else:
                raw_str = str(rdata)
            txt_val = raw_str.strip().strip("\"'").strip()
            found_values.append(txt_val)

            if expected_full:
                if secrets.compare_digest(txt_val, expected_full):
                    return "ok", f"Matched expected token '{txt_val}'", txt_host
            elif txt_val.startswith(txt_prefix):
                return "ok", f"Found valid token record '{txt_val}'", txt_host

        if found_values:
            return (
                "mismatch",
                f"TXT found but value mismatch (got: {', '.join(found_values)})",
                txt_host,
            )
        return "missing", "No TXT record found at hostname", txt_host

    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        return "missing", "NXDOMAIN or NoAnswer for TXT record", txt_host
    except Exception as exc:
        return "error", f"DNS query failed: {exc}", txt_host


async def check_cname_ingress(
    domain: str,
    target: str = DEFAULT_CNAME_TARGET,
    max_depth: int = DEFAULT_MAX_CNAME_DEPTH,
    timeout: float = DEFAULT_DNS_TIMEOUT,
    nameserver: str | None = None,
) -> tuple[str, str]:
    """Verify DNS proof-of-control: CNAME chain or apex A/AAAA match.

    Returns:
        tuple of (status, detail)
        status is one of: "ok", "mismatch", "no_record", "error"
    """
    import dns.resolver

    expected = target.lower().rstrip(".")
    current = domain.lower().rstrip(".")
    resolver = get_dns_resolver(timeout=timeout, nameserver=nameserver)

    # 1. Walk CNAME chain up to max_depth
    for hop in range(max_depth):
        try:
            answers = await asyncio.to_thread(resolver.resolve, current, "CNAME")
            cname_values = {str(rdata.target).rstrip(".").lower() for rdata in answers}
            if expected in cname_values:
                return "ok", f"CNAME correctly points to {expected} (hop {hop + 1})"
            if not cname_values:
                break
            current = next(iter(cname_values))
        except dns.resolver.NoAnswer:
            # End of CNAME chain at this hop; try apex A/AAAA check below
            break
        except dns.resolver.NXDOMAIN:
            return "mismatch", f"Domain {current} returned NXDOMAIN in CNAME lookup"
        except Exception as exc:
            return "error", f"CNAME resolution error: {exc}"

    # 2. Check apex / ALIAS A and AAAA records if no CNAME matched
    try:
        target_ips: set[str] = set()
        domain_ips: set[str] = set()

        with contextlib.suppress(Exception):
            for rdata in await asyncio.to_thread(resolver.resolve, expected, "A"):
                target_ips.add(str(rdata))
        with contextlib.suppress(Exception):
            for rdata in await asyncio.to_thread(resolver.resolve, expected, "AAAA"):
                target_ips.add(str(rdata))

        with contextlib.suppress(Exception):
            for rdata in await asyncio.to_thread(resolver.resolve, current, "A"):
                domain_ips.add(str(rdata))
        with contextlib.suppress(Exception):
            for rdata in await asyncio.to_thread(resolver.resolve, current, "AAAA"):
                domain_ips.add(str(rdata))

        if target_ips and domain_ips and target_ips == domain_ips:
            return (
                "ok",
                f"Apex A/AAAA records match ingress target IPs ({', '.join(sorted(domain_ips))})",
            )
        if domain_ips:
            return "mismatch", (
                f"Domain IPs ({', '.join(sorted(domain_ips))}) do not match "
                f"ingress IPs ({', '.join(sorted(target_ips)) or 'none'})"
            )
        return "no_record", f"No CNAME or A/AAAA records found for {domain}"
    except Exception as exc:
        return "error", f"A/AAAA resolution failed: {exc}"


async def probe_single_domain(
    target: DnsProbeTarget,
    cname_target: str = DEFAULT_CNAME_TARGET,
    txt_label: str = DEFAULT_TXT_LABEL,
    txt_prefix: str = DEFAULT_TXT_PREFIX,
    timeout: float = DEFAULT_DNS_TIMEOUT,
    nameserver: str | None = None,
) -> DnsProbeResult:
    """Run full synthetic probe (TXT and CNAME) for a target domain."""
    txt_status, txt_detail, txt_host = await check_txt_ownership(
        domain=target.domain,
        token=target.token,
        txt_label=txt_label,
        txt_prefix=txt_prefix,
        timeout=timeout,
        nameserver=nameserver,
    )

    cname_status, cname_detail = await check_cname_ingress(
        domain=target.domain,
        target=cname_target,
        timeout=timeout,
        nameserver=nameserver,
    )

    passed = (txt_status == "ok") and (cname_status == "ok")

    return DnsProbeResult(
        domain=target.domain,
        txt_host=txt_host,
        txt_status=txt_status,
        txt_detail=txt_detail,
        cname_target=cname_target,
        cname_status=cname_status,
        cname_detail=cname_detail,
        passed=passed,
    )


def load_targets_from_db() -> list[DnsProbeTarget]:
    """Load active custom domains directly from PostgreSQL database."""
    try:
        from sqlalchemy import select

        from app.db.session import SessionLocal
        from app.models.workspaces import WorkspaceApp

        targets: list[DnsProbeTarget] = []
        with SessionLocal() as session:
            stmt = select(WorkspaceApp).where(
                WorkspaceApp.custom_domain.isnot(None),
                WorkspaceApp.custom_domain_status == "active",
            )
            apps = session.execute(stmt).scalars().all()
            for app in apps:
                if app.custom_domain:
                    targets.append(
                        DnsProbeTarget(
                            domain=app.custom_domain,
                            token=app.custom_domain_verify_token,
                            app_id=str(app.id),
                            workspace_id=app.workspace_id,
                        )
                    )
        return targets
    except Exception as exc:
        logging.warning("Could not load domains from database: %s", exc)
        return []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synthetic DNS probe for custom domain TXT ownership and CNAME ingress.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-d",
        "--domains",
        nargs="+",
        help="One or more custom domains to probe (e.g. app.domain.com shop.brand.vn).",
    )
    parser.add_argument(
        "-t",
        "--token",
        help="Optional expected verification token (used when checking a single domain).",
    )
    parser.add_argument(
        "-p",
        "--pair",
        action="append",
        dest="pairs",
        help="Domain and verification token pair formatted as 'domain:token'. Can be specified multiple times.",
    )
    parser.add_argument(
        "--cname-target",
        default=os.getenv("CNAME_INGRESS_HOST", DEFAULT_CNAME_TARGET),
        help="Expected CNAME ingress host target.",
    )
    parser.add_argument(
        "--txt-label",
        default=os.getenv("WEB_BUILDER_TXT_VERIFY_LABEL", DEFAULT_TXT_LABEL),
        help="TXT verify subdomain label.",
    )
    parser.add_argument(
        "--txt-prefix",
        default=os.getenv("WEB_BUILDER_TXT_VERIFY_PREFIX", DEFAULT_TXT_PREFIX),
        help="Expected prefix of the TXT verification record value.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_DNS_TIMEOUT,
        help="DNS query timeout in seconds.",
    )
    parser.add_argument(
        "--nameserver",
        help="Optional custom DNS resolver nameserver (e.g. 8.8.8.8 or 1.1.1.1).",
    )
    parser.add_argument(
        "--check-db",
        action="store_true",
        help="Fetch active verified custom domains from the database.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Quiet mode: suppress detailed progress, output only summary.",
    )
    return parser.parse_args()


async def main_async() -> int:
    args = parse_args()
    targets: list[DnsProbeTarget] = []

    # 1. Collect targets from CLI arguments
    if args.pairs:
        for pair in args.pairs:
            if ":" in pair:
                dom, tok = pair.split(":", 1)
                targets.append(DnsProbeTarget(domain=dom.strip(), token=tok.strip()))
            else:
                targets.append(DnsProbeTarget(domain=pair.strip()))

    if args.domains:
        for d in args.domains:
            targets.append(DnsProbeTarget(domain=d.strip(), token=args.token))

    # 2. Collect targets from DB if requested
    if args.check_db:
        db_targets = load_targets_from_db()
        if not args.quiet and not args.json:
            print(f"Loaded {len(db_targets)} active custom domain(s) from database.")
        targets.extend(db_targets)

    # Fallback if no target specified
    if not targets:
        print(
            "Error: No domains to probe. Provide --domains, --pair, or --check-db.\n"
            "Run with --help for usage.",
            file=sys.stderr,
        )
        return 1

    # Run probes concurrently
    tasks = [
        probe_single_domain(
            target=t,
            cname_target=args.cname_target,
            txt_label=args.txt_label,
            txt_prefix=args.txt_prefix,
            timeout=args.timeout,
            nameserver=args.nameserver,
        )
        for t in targets
    ]
    results: list[DnsProbeResult] = await asyncio.gather(*tasks)

    all_passed = all(r.passed for r in results)
    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count

    if args.json:
        payload = {
            "summary": {
                "total": len(results),
                "passed": passed_count,
                "failed": failed_count,
                "all_passed": all_passed,
            },
            "results": [r.to_dict() for r in results],
        }
        print(json.dumps(payload, indent=2))
        return 0 if all_passed else 1

    # Human-readable output
    print("=" * 80)
    print("NOWING SYNTHETIC DNS PROBE REPORT")
    print(f"Ingress Target: {args.cname_target}")
    print(f"TXT Label     : {args.txt_label}")
    print("=" * 80)

    for r in results:
        status_icon = "✓ PASS" if r.passed else "✗ FAIL"
        print(f"\n[{status_icon}] Domain: {r.domain}")
        print(f"  • TXT Record   : [{r.txt_status.upper()}] host={r.txt_host}")
        print(f"    Detail       : {r.txt_detail}")
        print(f"  • CNAME Ingress: [{r.cname_status.upper()}] target={r.cname_target}")
        print(f"    Detail       : {r.cname_detail}")

    print("\n" + "-" * 80)
    print(f"SUMMARY: {passed_count}/{len(results)} passed ({failed_count} failed)")
    print("-" * 80)

    return 0 if all_passed else 1


def main() -> None:
    try:
        sys.exit(asyncio.run(main_async()))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
