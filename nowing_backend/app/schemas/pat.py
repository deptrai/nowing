from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# PAT Scopes
LEADS_CLIPPER_WRITE_SCOPE: str = "leads:clipper:write"

# Catalog chung cho mọi token_kind (AI-42.7 + AI-42.4): PAT scope = permission
# string (identity map — unified seam trong check_permission dùng chính
# required_permission làm scope). Vì vậy catalog = mọi Permission enum +
# agent_chat:* + clipper scope tùy ý (không phải Permission).
def _build_known_scopes() -> list[str]:
    from app.db.enums import Permission  # local import — tránh vòng import

    scopes = {LEADS_CLIPPER_WRITE_SCOPE}
    # agent_chat scopes (frozenset[str] ở app/auth/agent_chat.py:22 — không
    # import module để tránh kéo deps auth vào schemas).
    scopes.update(
        {
            "agent_chat:thread:create",
            "agent_chat:message:create",
            "agent_chat:thread:read",
        }
    )
    scopes.update(getattr(p, "value", p) for p in Permission)
    return sorted(scopes)


KNOWN_PAT_SCOPES: list[str] = _build_known_scopes()


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
