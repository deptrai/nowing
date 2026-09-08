"""SQLAlchemy ORM models split by domain.

Import this package (or specific modules) to register all tables on
``Base.metadata`` for Alembic and startup schema creation.
"""

from __future__ import annotations

# Domain model submodules (imported to register tables on Base.metadata)
from app.models import (
    admin_health as admin_health,
    billing as billing,
    bulk_ops as bulk_ops,
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
    workspaces as workspaces,
)

__all__ = [
    "admin_health",
    "billing",
    "bulk_ops",
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
    "workspaces",
]
