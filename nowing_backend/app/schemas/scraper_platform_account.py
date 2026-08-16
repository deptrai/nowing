"""Pydantic schemas for scraper platform account admin API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class TelegramRequestOtpRequest(BaseModel):
    phone: str = Field(
        ...,
        description="Phone number with international country code (e.g. +84988123456)",
    )
    api_id: int = Field(..., description="Telegram API ID from my.telegram.org")
    api_hash: str = Field(..., description="Telegram API Hash from my.telegram.org")
    proxy_url: str | None = Field(
        default=None,
        description="Optional SOCKS5 proxy URL (e.g. socks5h://user:pass@host:port)",
    )
    label: str | None = Field(
        default=None, description="Display label for the scraper account"
    )

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, v: str) -> str:
        return "".join(v.split())

    @field_validator("api_hash")
    @classmethod
    def clean_api_hash(cls, v: str) -> str:
        return v.strip()


class TelegramVerifyOtpRequest(BaseModel):
    phone: str = Field(..., description="Phone number being verified")
    code: str = Field(..., description="SMS / Telegram authentication OTP code")

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, v: str) -> str:
        return "".join(v.split())

    @field_validator("code")
    @classmethod
    def clean_code(cls, v: str) -> str:
        return v.strip()


class TelegramVerify2FaRequest(BaseModel):
    phone: str = Field(..., description="Phone number being verified")
    password: str = Field(..., description="Telegram 2FA Cloud Password")

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, v: str) -> str:
        return "".join(v.split())

    @field_validator("password")
    @classmethod
    def clean_password(cls, v: str) -> str:
        return v.strip()


class TelegramAuthResponse(BaseModel):
    status: str = Field(
        ..., description="Status: 'otp_sent', 'authenticated', or '2fa_required'"
    )
    phone: str
    account_id: int | None = None
    hint: str | None = None
    message: str | None = None
