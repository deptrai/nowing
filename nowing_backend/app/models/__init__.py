"""SQLAlchemy ORM models split by domain.

Import this package (or specific modules) to register all tables on
``Base.metadata`` for Alembic and startup schema creation.
"""

from __future__ import annotations

# Domain model submodules (imported to register tables on Base.metadata)
# NOTE: app.db.base được bootstrap trước qua leads để tránh circular import
# (app.db/__init__ import tên từ app.models.campaigns).
from app.models import (
    admin_health as admin_health,
    billing as billing,
    browser_operator_audit as browser_operator_audit,
    bulk_ops as bulk_ops,
    campaigns as campaigns,
    chat as chat,
    connectors as connectors,
    documents as documents,
    leads as leads,
    memory as memory,
    memory_review_queue as memory_review_queue,
    memory_source_legal_tier as memory_source_legal_tier,
    presentations as presentations,
    projects as projects,
    scraper as scraper,
    users as users,
    webset_campaign as webset_campaign,
    workspaces as workspaces,
)

# Explicit re-exports (spec 44.1: `from app.models import LeadCampaign` phải chạy).
from app.models.campaigns import (
    CampaignLead as CampaignLead,
    CampaignRun as CampaignRun,
    LeadCampaign as LeadCampaign,
)

__all__ = [
    "admin_health",
    "billing",
    "browser_operator_audit",
    "bulk_ops",
    "campaigns",
    "chat",
    "connectors",
    "documents",
    "leads",
    "memory",
    "memory_review_queue",
    "memory_source_legal_tier",
    "presentations",
    "projects",
    "scraper",
    "users",
    "webset_campaign",
    "workspaces",
]
