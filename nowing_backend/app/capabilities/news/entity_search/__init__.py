"""``news.entity_search`` package."""

from __future__ import annotations

from app.capabilities.news.entity_search.definition import NEWS_ENTITY_SEARCH
from app.capabilities.news.entity_search.executor import (
    EntitySearchExecutor,
    build_entity_search_executor,
)
from app.capabilities.news.entity_search.schemas import (
    EntitySearchInput,
    EntitySearchOutput,
)

__all__ = [
    "NEWS_ENTITY_SEARCH",
    "EntitySearchExecutor",
    "EntitySearchInput",
    "EntitySearchOutput",
    "build_entity_search_executor",
]
