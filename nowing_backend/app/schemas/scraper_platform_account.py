"""Pydantic schemas for scraper platform account admin API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScraperPlatformAccountCredentials(BaseModel):
    """Open-ended credential bag; UI may store cookies, tokens, or API keys."""

    model_config = ConfigDict(extra="allow")

    cookies: str | None = Field(
        default=None,
        description="Browser cookie string for the platform.",
    )
    token: str | None = Field(
        default=None,
        description="Bearer / API token if the platform supports one.",
    )


class ScraperPlatformAccountCreate(BaseModel):
    platform: str = Field(..., min_length=1, max_length=64)
    label: str | None = Field(default=None, max_length=255)
    is_enabled: bool = True
    is_default: bool = False
    credentials: ScraperPlatformAccountCredentials | None = None


class ScraperPlatformAccountUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=255)
    is_enabled: bool | None = None
    is_default: bool | None = None
    credentials: ScraperPlatformAccountCredentials | None = None


class ScraperPlatformAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    label: str | None
    is_enabled: bool
    is_default: bool
    credentials: ScraperPlatformAccountCredentials | None = None
    created_at: Any
    updated_at: Any
