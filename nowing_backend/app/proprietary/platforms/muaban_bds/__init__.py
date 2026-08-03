"""Muaban.net BĐS platform package."""

from __future__ import annotations

from app.proprietary.platforms.muaban_bds.schemas import (
    MuabanBdsListing,
    MuabanBdsScrapeInput,
    MuabanBdsScrapeOutput,
)
from app.proprietary.platforms.muaban_bds.scraper import scrape_muaban_bds

__all__ = [
    "MuabanBdsListing",
    "MuabanBdsScrapeInput",
    "MuabanBdsScrapeOutput",
    "scrape_muaban_bds",
]
