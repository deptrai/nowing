"""DNS services package."""

from app.services.dns.synthetic_probe_service import (
    DomainProbeReport,
    ProbeResult,
    SyntheticDnsProbeService,
    probe_domain,
    verify_cname_record,
    verify_txt_record,
)

__all__ = [
    "DomainProbeReport",
    "ProbeResult",
    "SyntheticDnsProbeService",
    "probe_domain",
    "verify_cname_record",
    "verify_txt_record",
]
