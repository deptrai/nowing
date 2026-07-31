import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db import ConnectionScope


class AdminGlobalModelPricing(BaseModel):
    """Pricing/rate metadata for a managed global model."""

    cost_per_1k_input_tokens: float | None = None
    cost_per_1k_output_tokens: float | None = None
    rpm: int | None = None
    tpm: int | None = None
    quality_score: int | None = None
    auto_pin_tier: str | None = None
    router_pool_eligible: bool = True
    base_model: str | None = None


class AdminGlobalModelSelection(BaseModel):
    model_id: str = Field(..., max_length=255)
    display_name: str | None = Field(None, max_length=255)
    supports_chat: bool = True
    max_input_tokens: int | None = None
    supports_image_input: bool | None = None
    supports_tools: bool | None = None
    supports_image_generation: bool | None = None
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    billing_tier: str | None = Field(None, max_length=50)
    base_model: str | None = Field(None, max_length=255)
    pricing: AdminGlobalModelPricing = Field(default_factory=AdminGlobalModelPricing)


class AdminGlobalConnectionCreate(BaseModel):
    provider: str = Field(..., max_length=100)
    base_url: str | None = Field(None, max_length=500)
    api_key: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    models: list[AdminGlobalModelSelection] = Field(default_factory=list)


class AdminGlobalConnectionUpdate(BaseModel):
    provider: str | None = Field(None, max_length=100)
    base_url: str | None = Field(None, max_length=500)
    api_key: str | None = None
    extra: dict[str, Any] | None = None
    enabled: bool | None = None


class AdminGlobalModelUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=255)
    enabled: bool | None = None
    supports_chat: bool | None = None
    max_input_tokens: int | None = None
    supports_image_input: bool | None = None
    supports_tools: bool | None = None
    supports_image_generation: bool | None = None
    capabilities_override: dict[str, Any] | None = None
    billing_tier: str | None = Field(None, max_length=50)
    base_model: str | None = Field(None, max_length=255)
    pricing: AdminGlobalModelPricing | None = None


class AdminGlobalModelRead(BaseModel):
    id: int
    connection_id: int
    model_id: str
    display_name: str | None = None
    source: str = "managed"
    can_edit: bool = False
    can_delete: bool = False
    supports_chat: bool | None = None
    max_input_tokens: int | None = None
    supports_image_input: bool | None = None
    supports_tools: bool | None = None
    supports_image_generation: bool | None = None
    capabilities_override: dict[str, Any] = Field(default_factory=dict)
    enabled: bool
    billing_tier: str | None = None
    base_model: str | None = None
    catalog: dict[str, Any] = Field(default_factory=dict)
    cost_per_1k_input_tokens: float | None = None
    cost_per_1k_output_tokens: float | None = None
    rpm: int | None = None
    tpm: int | None = None
    quality_score: int | None = None
    auto_pin_tier: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminGlobalConnectionRead(BaseModel):
    id: int
    provider: str
    base_url: str | None = None
    api_key: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    scope: ConnectionScope | str = ConnectionScope.GLOBAL
    workspace_id: int | None = None
    user_id: uuid.UUID | None = None
    enabled: bool
    has_api_key: bool
    source: str = "managed"
    can_edit: bool = False
    can_delete: bool = False
    models: list[AdminGlobalModelRead] = Field(default_factory=list)
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminGlobalModelTest(BaseModel):
    model_id: str = Field(..., max_length=255)


class AdminGlobalModelTestPreview(AdminGlobalConnectionCreate):
    """Combined connection draft + model id for the test-preview endpoint."""

    model_id: str = Field(..., max_length=255)


class AdminGlobalModelsBulkUpdate(BaseModel):
    model_ids: list[int] = Field(..., min_length=1, max_length=1000)
    enabled: bool
