"""Universal lead source adapters package (Story 21.15)."""

from app.lead_intelligence.adapters.base import (
    ContactCandidate,
    LeadSourceAdapter,
    LeadSourceCategory,
    NormalizedLead,
    RawLeadRecord,
    extract_phones_from_text,
    normalize_vietnamese_phone,
)
from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter
from app.lead_intelligence.adapters.chotot import ChototLeadAdapter
from app.lead_intelligence.adapters.enterprise import EnterpriseProcurementLeadAdapter
from app.lead_intelligence.adapters.job_market import JobMarketLeadAdapter
from app.lead_intelligence.adapters.muaban_bds import MuabanBdsLeadAdapter
from app.lead_intelligence.adapters.muasamcong import MuaSamCongLeadAdapter
from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
from app.lead_intelligence.adapters.social import SocialLeadAdapter
from app.lead_intelligence.adapters.vietnamworks import VietnamWorksLeadAdapter
from app.lead_intelligence.adapters.vn_jobs import VnJobsLeadAdapter

__all__ = [
    "BatdongsanLeadAdapter",
    "ChototLeadAdapter",
    "ContactCandidate",
    "EnterpriseProcurementLeadAdapter",
    "JobMarketLeadAdapter",
    "LeadSourceAdapter",
    "LeadSourceAdapterRegistry",
    "LeadSourceCategory",
    "MuaSamCongLeadAdapter",
    "MuabanBdsLeadAdapter",
    "NormalizedLead",
    "RawLeadRecord",
    "SocialLeadAdapter",
    "VietnamWorksLeadAdapter",
    "VnJobsLeadAdapter",
    "extract_phones_from_text",
    "normalize_vietnamese_phone",
]
