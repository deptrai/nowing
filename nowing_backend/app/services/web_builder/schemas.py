"""Pydantic schemas for Web Builder Service (Story 27.1 / AD-113 / AD-114)."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class GeneratedProjectFile(BaseModel):
    """A single file generated as part of a Next.js web application."""

    path: str = Field(
        ..., description="Relative file path inside the project repository"
    )
    content: str = Field(..., description="File content (UTF-8 encoded string)")


class GeneratedProjectSpec(BaseModel):
    """Structured LLM specification output for a generated web application."""

    name: str = Field(..., description="Human-readable application name")
    slug: str = Field(..., description="URL-safe application identifier slug")
    description: str | None = Field(None, description="Brief description of the app")
    files: list[GeneratedProjectFile] = Field(
        default_factory=list, description="Array of project files"
    )


class WebAppBuildInput(BaseModel):
    """Input payload for generating a web application from prompt."""

    prompt: str = Field(
        ..., min_length=3, description="Natural language description of the web app"
    )
    language: str = Field(default="en", description="Target UI language (e.g. en, vi)")
    workspace_id: int = Field(..., description="Owning workspace ID")
    user_id: int | None = Field(default=None, description="Requesting user ID")
    app_name: str | None = Field(
        default=None, description="Optional custom name override"
    )


class WebAppBuildOutput(BaseModel):
    """Output payload after generating a web application."""

    app_id: str
    workspace_id: int
    name: str
    slug: str
    status: (
        str  # generated, validation_failed, building, published, deploy_failed, error
    )
    preview_url: str | None = None
    public_url: str | None = None
    message: str | None = None
    files: list[str] = Field(
        default_factory=list, description="List of generated file paths"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WebAppDeployInput(BaseModel):
    """Input payload for 1-click publishing an application."""

    workspace_id: int
    slug: str | None = None


class WebAppDeployOutput(BaseModel):
    """Output payload after publishing an application container & route."""

    app_id: str
    workspace_id: int
    status: str  # published, deploy_failed, error
    public_url: str | None = None
    slug: str
    message: str | None = None


class CustomDomainInput(BaseModel):
    """Input payload for binding a custom CNAME domain."""

    workspace_id: int
    custom_domain: str = Field(
        ..., min_length=3, description="FQDN hostname (e.g. app.mycompany.com)"
    )


class CustomDomainOutput(BaseModel):
    """Output payload after configuring custom domain."""

    app_id: str
    workspace_id: int
    custom_domain: str
    status: str  # active, pending_verification, failed
    cname_target: str
    message: str | None = None


class MarkToolPatch(BaseModel):
    """Patch operation for Design View Mark Tool."""

    type: str = Field(
        ..., description="Patch type: text, className, attribute, replace"
    )
    value: str = Field(..., description="New replacement value or code snippet")
    attribute: str | None = Field(
        None, description="Attribute name if type is attribute"
    )


class MarkToolInput(BaseModel):
    """Input payload for Mark Tool visual edit."""

    workspace_id: int
    selector: str = Field(
        ..., description="DOM selector (CSS or XPath) captured from iframe"
    )
    patch: MarkToolPatch = Field(..., description="Patch details")
    file_path: str = Field(
        default="app/page.tsx", description="Target component file path"
    )


class MarkToolOutput(BaseModel):
    """Output payload after applying Mark Tool mutation."""

    app_id: str
    workspace_id: int
    status: str  # patched, mark_unresolvable, error
    file_path: str
    patched_code: str | None = None
    message: str | None = None


class WorkspaceAppRead(BaseModel):
    """Public read schema for a WorkspaceApp entity."""

    id: str
    workspace_id: int
    user_id: int | None
    name: str
    slug: str
    description: str | None = None
    prompt: str | None = None
    language: str
    status: str
    preview_url: str | None = None
    public_url: str | None = None
    custom_domain: str | None = None
    custom_domain_status: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
