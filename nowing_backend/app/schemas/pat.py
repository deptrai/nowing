from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# PAT Scopes
LEADS_CLIPPER_WRITE_SCOPE: str = "leads:clipper:write"
KNOWN_PAT_SCOPES: list[str] = [
    LEADS_CLIPPER_WRITE_SCOPE,
    "agent_chat:thread:create",
    "agent_chat:message:create",
    "agent_chat:thread:read",
]


class PATCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    expires_in_days: int | None = Field(default=None, gt=0)
    token_kind: str = Field(default="legacy")
    workspace_id: int | None = Field(default=None)
    client_id: str | None = Field(default=None, min_length=1, max_length=63)
    agent_id: str | None = Field(default=None, min_length=1, max_length=63)
    scopes: list[str] = Field(default_factory=list)


class PATCreated(BaseModel):
    id: int
    label: str
    token: str
    prefix: str
    expires_at: datetime | None = None
    token_kind: str
    workspace_id: int | None = None
    client_id: str | None = None
    agent_id: str | None = None
    scopes: list[str]


class PATRead(BaseModel):
    id: int
    label: str
    prefix: str
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime
    token_kind: str
    workspace_id: int | None = None
    client_id: str | None = None
    agent_id: str | None = None
    scopes: list[str]

    model_config = ConfigDict(from_attributes=True)
