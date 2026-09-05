"""SQLAlchemy ORM models split by domain.

Import this package (or specific modules) to register all tables on
``Base.metadata`` for Alembic and startup schema creation.
"""

from __future__ import annotations

# Domain model submodules (imported to register tables on Base.metadata)
from app.models import (
    admin_health as admin_health,
    billing as billing,
    chat as chat,
    connectors as connectors,
    documents as documents,
    leads as leads,
    memory as memory,
    presentations as presentations,
    projects as projects,
    scraper as scraper,
    users as users,
    workspaces as workspaces,
)

__all__ = [
    "admin_health",
    "billing",
    "chat",
    "connectors",
    "documents",
    "leads",
    "memory",
    "presentations",
    "projects",
    "scraper",
    "users",
    "workspaces",
]
