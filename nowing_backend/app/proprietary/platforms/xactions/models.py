"""Shared dataclasses for XActions ingress."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class SocialPostData:
    platform: str
    external_post_id: str
    author_id: str | None = None
    author_name: str | None = None
    author_url: str | None = None
    post_url: str | None = None
    content: str | None = None
    intent_tag: str | None = None
    fit_score: float = 0.0
    reactions_count: int = 0
    comments_count: int = 0
    shares_count: int = 0
    media_urls: list[str] = field(default_factory=list)
    raw_entities: dict[str, Any] = field(default_factory=dict)
    published_at: datetime | None = None
    target_id: int | None = None
    workspace_id: int | None = None
    client_id: str | None = None
    # Thin-event payload fields (Story 21.8a)
    category: str | None = None
    storage_ref: str | None = None
    scraper_id: str | None = None
    benchmark_health: str | None = None
    benchmark_alert: bool | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.published_at:
            data["published_at"] = self.published_at.isoformat()
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class SocialMonitoredTargetData:
    platform: str
    target_id: str
    target_name: str
    target_url: str | None = None
    category: str = "general"
    is_active: bool = True
    realtime_stream: bool = False
    scrape_interval_minutes: int = 15
    status: str = "active"
    account_id: str | None = None
    proxy_url: str | None = None
