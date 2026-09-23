"""Pydantic schemas for Admin Bulk Operations Console (Story 29.4 / AD-54)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field

from app.models.bulk_ops import BulkAction

FilterOperator = Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in"]


class FilterClause(BaseModel):
    """A single filter clause in a structured filter specification."""

    field: str = Field(..., min_length=1, max_length=64)
    operator: FilterOperator = Field(..., alias="op")
    value: Any

    model_config = ConfigDict(populate_by_name=True)


class DryRunRequest(BaseModel):
    action: BulkAction
    filter_spec: list[FilterClause] = Field(default_factory=list)
    action_params: dict[str, Any] = Field(default_factory=dict)
    workspace_id: int | None = None


class DryRunResponse(BaseModel):
    action: BulkAction
    total_count: int
    sample_subjects: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    can_execute: bool = True

    model_config = ConfigDict(populate_by_name=True)

    @computed_field
    @property
    def affected_count(self) -> int:
        return self.total_count

    @computed_field
    @property
    def sample_affected(self) -> list[dict[str, Any]]:
        return self.sample_subjects


class ExecuteRequest(BaseModel):
    action: BulkAction
    filter_spec: list[FilterClause] = Field(default_factory=list)
    action_params: dict[str, Any] = Field(default_factory=dict)
    workspace_id: int | None = None
    # High-risk re-authentication fields
    password: str | None = None
    mfa_token: str | None = None


class ExecuteResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    action: BulkAction
    message: str = "Job queued successfully"


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    job_id: uuid.UUID = Field(..., validation_alias=AliasChoices("id", "job_id"))
    action: str
    status: str
    actor_id: uuid.UUID | None = None
    workspace_id: int | None = None
    filter_spec: list[dict[str, Any]] = Field(default_factory=list)
    action_params: dict[str, Any] = Field(default_factory=dict)
    total_count: int = 0
    processed_count: int = 0
    affected_count: int = 0
    error_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    error_message: str | None = None
    cancelable: bool = False

    @computed_field
    @property
    def is_cancelable(self) -> bool:
        return self.cancelable


class BulkOpErrorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: uuid.UUID
    subject_type: str
    subject_id: str
    error_message: str
    retryable: bool
    created_at: datetime


class CancelJobResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    message: str
