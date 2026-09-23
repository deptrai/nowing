"""Models for the users domain."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi_users.db import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
)
from sqlalchemy import (
    ARRAY,
    TIMESTAMP,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, relationship

from app.config import config
from app.db.base import Base, BaseModel, TimestampMixin

if config.AUTH_TYPE == "GOOGLE":

    class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
        pass

    class User(SQLAlchemyBaseUserTableUUID, Base):
        oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
            "OAuthAccount", lazy="joined"
        )
        workspaces = relationship("Workspace", back_populates="user")
        notifications = relationship(
            "Notification",
            back_populates="user",
            order_by="Notification.created_at.desc()",
            cascade="all, delete-orphan",
        )

        # RBAC relationships
        workspace_memberships = relationship(
            "WorkspaceMembership",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        created_invites = relationship(
            "WorkspaceInvite",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Chat threads created by this user
        new_chat_threads = relationship(
            "NewChatThread",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Documents created/uploaded by this user
        documents = relationship(
            "Document",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Folders created by this user
        folders = relationship(
            "Folder",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Image generations created by this user
        image_generations = relationship(
            "ImageGeneration",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Connectors created by this user
        search_source_connectors = relationship(
            "SearchSourceConnector",
            back_populates="user",
            passive_deletes=True,
        )

        connections = relationship(
            "Connection",
            back_populates="user",
            passive_deletes=True,
        )

        # Automations created by this user
        automations = relationship(
            "Automation",
            back_populates="created_by",
            passive_deletes=True,
        )

        playbooks = relationship(
            "Playbook",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Incentive tasks completed by this user
        incentive_tasks = relationship(
            "UserIncentiveTask",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        page_purchases = relationship(
            "PagePurchase",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        credit_purchases = relationship(
            "CreditPurchase",
            back_populates="user",
            cascade="all, delete-orphan",
        )

        # Unified credit wallet (USD micro-units, 1_000_000 == $1.00).
        # Decreases on use (ETL pages + premium model calls), increases on
        # purchase / incentive grant / auto-reload. May dip slightly negative
        # when an actual cost exceeds its pre-charge estimate; UI clamps at $0.
        credit_micros_balance = Column(
            BigInteger,
            nullable=False,
            default=config.DEFAULT_CREDIT_MICROS_BALANCE,
            server_default=str(config.DEFAULT_CREDIT_MICROS_BALANCE),
        )
        # In-flight reservation holds (released/settled at finalize).
        credit_micros_reserved = Column(
            BigInteger, nullable=False, default=0, server_default="0"
        )

        # Auto-reload (off-session Stripe top-up), behind AUTO_RELOAD_ENABLED.
        # ``stripe_customer_id`` + ``auto_reload_payment_method_id`` are the
        # saved-card plumbing; thresholds are micro-USD. ``auto_reload_failed_at``
        # is set (and ``auto_reload_enabled`` flipped off) when an off-session
        # charge is declined so the UI can prompt the user to fix their card.
        stripe_customer_id = Column(String, nullable=True)
        auto_reload_enabled = Column(
            Boolean, nullable=False, default=False, server_default="false"
        )
        auto_reload_threshold_micros = Column(BigInteger, nullable=True)
        auto_reload_amount_micros = Column(BigInteger, nullable=True)
        auto_reload_payment_method_id = Column(String, nullable=True)
        auto_reload_failed_at = Column(TIMESTAMP(timezone=True), nullable=True)

        # User profile from OAuth
        display_name = Column(String, nullable=True)
        avatar_url = Column(String, nullable=True)

        last_login = Column(TIMESTAMP(timezone=True), nullable=True)

        notification_preferences = Column(
            JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
        )

        # Refresh tokens for this user
        refresh_tokens = relationship(
            "RefreshToken",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        personal_access_tokens = relationship(
            "PersonalAccessToken",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        # Memory created by this user
        memories = relationship(
            "Memory",
            back_populates="created_by",
            passive_deletes=True,
        )
        memory_versions = relationship(
            "MemoryVersion",
            back_populates="corrected_by",
            passive_deletes=True,
        )
        research_threads = relationship(
            "ResearchThread",
            back_populates="created_by",
            passive_deletes=True,
        )

else:

    class User(SQLAlchemyBaseUserTableUUID, Base):
        workspaces = relationship("Workspace", back_populates="user")
        notifications = relationship(
            "Notification",
            back_populates="user",
            order_by="Notification.created_at.desc()",
            cascade="all, delete-orphan",
        )

        # RBAC relationships
        workspace_memberships = relationship(
            "WorkspaceMembership",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        created_invites = relationship(
            "WorkspaceInvite",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Chat threads created by this user
        new_chat_threads = relationship(
            "NewChatThread",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Documents created/uploaded by this user
        documents = relationship(
            "Document",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Folders created by this user
        folders = relationship(
            "Folder",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Image generations created by this user
        image_generations = relationship(
            "ImageGeneration",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Connectors created by this user
        search_source_connectors = relationship(
            "SearchSourceConnector",
            back_populates="user",
            passive_deletes=True,
        )

        connections = relationship(
            "Connection",
            back_populates="user",
            passive_deletes=True,
        )

        # Automations created by this user
        automations = relationship(
            "Automation",
            back_populates="created_by",
            passive_deletes=True,
        )

        playbooks = relationship(
            "Playbook",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Incentive tasks completed by this user
        incentive_tasks = relationship(
            "UserIncentiveTask",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        page_purchases = relationship(
            "PagePurchase",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        credit_purchases = relationship(
            "CreditPurchase",
            back_populates="user",
            cascade="all, delete-orphan",
        )

        # Unified credit wallet (USD micro-units, 1_000_000 == $1.00).
        # Decreases on use (ETL pages + premium model calls), increases on
        # purchase / incentive grant / auto-reload. May dip slightly negative
        # when an actual cost exceeds its pre-charge estimate; UI clamps at $0.
        credit_micros_balance = Column(
            BigInteger,
            nullable=False,
            default=config.DEFAULT_CREDIT_MICROS_BALANCE,
            server_default=str(config.DEFAULT_CREDIT_MICROS_BALANCE),
        )
        # In-flight reservation holds (released/settled at finalize).
        credit_micros_reserved = Column(
            BigInteger, nullable=False, default=0, server_default="0"
        )

        # Auto-reload (off-session Stripe top-up), behind AUTO_RELOAD_ENABLED.
        # ``stripe_customer_id`` + ``auto_reload_payment_method_id`` are the
        # saved-card plumbing; thresholds are micro-USD. ``auto_reload_failed_at``
        # is set (and ``auto_reload_enabled`` flipped off) when an off-session
        # charge is declined so the UI can prompt the user to fix their card.
        stripe_customer_id = Column(String, nullable=True)
        auto_reload_enabled = Column(
            Boolean, nullable=False, default=False, server_default="false"
        )
        auto_reload_threshold_micros = Column(BigInteger, nullable=True)
        auto_reload_amount_micros = Column(BigInteger, nullable=True)
        auto_reload_payment_method_id = Column(String, nullable=True)
        auto_reload_failed_at = Column(TIMESTAMP(timezone=True), nullable=True)

        # User profile (can be set manually for non-OAuth users)
        display_name = Column(String, nullable=True)
        avatar_url = Column(String, nullable=True)

        last_login = Column(TIMESTAMP(timezone=True), nullable=True)

        notification_preferences = Column(
            JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
        )

        # Refresh tokens for this user
        refresh_tokens = relationship(
            "RefreshToken",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        personal_access_tokens = relationship(
            "PersonalAccessToken",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        # Memory created by this user
        memories = relationship(
            "Memory",
            back_populates="created_by",
            passive_deletes=True,
        )
        memory_versions = relationship(
            "MemoryVersion",
            back_populates="corrected_by",
            passive_deletes=True,
        )
        research_threads = relationship(
            "ResearchThread",
            back_populates="created_by",
            passive_deletes=True,
        )



class WorkspaceRole(BaseModel, TimestampMixin):
    """
    Custom roles that can be defined per workspace.
    Each workspace can have multiple roles with different permission sets.
    """

    __tablename__ = "workspace_roles"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "name",
            name="uq_workspace_role_name",
        ),
    )

    name = Column(String(100), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    # List of Permission enum values (e.g., ["documents:read", "chats:create"])
    permissions = Column(ARRAY(String), nullable=False, default=[])
    # Whether this role is assigned to new members by default when they join via invite
    is_default = Column(Boolean, nullable=False, default=False)
    # System roles (Owner, Editor, Viewer) cannot be deleted
    is_system_role = Column(Boolean, nullable=False, default=False)

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace = relationship("Workspace", back_populates="roles")

    memberships = relationship(
        "WorkspaceMembership", back_populates="role", passive_deletes=True
    )
    invites = relationship(
        "WorkspaceInvite", back_populates="role", passive_deletes=True
    )



class WorkspaceMembership(BaseModel, TimestampMixin):
    """
    Tracks user membership in workspaces with their assigned role.
    Each user can be a member of multiple workspaces with different roles.
    """

    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "workspace_id",
            name="uq_user_workspace_membership",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id = Column(
        Integer,
        ForeignKey("workspace_roles.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Indicates if this user is the original creator/owner of the workspace
    is_owner = Column(Boolean, nullable=False, default=False)
    # Timestamp when the user joined (via invite or as creator)
    joined_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    # Reference to the invite used to join (null if owner/creator)
    invited_by_invite_id = Column(
        Integer,
        ForeignKey("workspace_invites.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Monthly spend cap and lead distribution settings (Story 24.3 / INV-24.4)
    monthly_spend_cap_micros = Column(BigInteger, nullable=True)
    monthly_spent_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    is_accepting_leads = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    lead_capacity = Column(Integer, nullable=False, default=50, server_default="50")
    status = Column(
        String(20), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )

    user = relationship("User", back_populates="workspace_memberships")
    workspace = relationship("Workspace", back_populates="memberships")
    role = relationship("WorkspaceRole", back_populates="memberships")
    invited_by_invite = relationship(
        "WorkspaceInvite", back_populates="used_by_memberships"
    )



class WorkspaceInvite(BaseModel, TimestampMixin):
    """
    Invite links for workspaces.
    Users can create invite links with specific roles that others can use to join.
    """

    __tablename__ = "workspace_invites"

    # Unique invite code (used in invite URLs)
    invite_code = Column(String(64), nullable=False, unique=True, index=True)

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Role to assign when invite is used (null means use default role)
    role_id = Column(
        Integer,
        ForeignKey("workspace_roles.id", ondelete="SET NULL"),
        nullable=True,
    )
    # User who created this invite
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Expiration timestamp (null means never expires)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    # Maximum number of times this invite can be used (null means unlimited)
    max_uses = Column(Integer, nullable=True)
    # Number of times this invite has been used
    uses_count = Column(Integer, nullable=False, default=0)
    # Whether this invite is currently active
    is_active = Column(Boolean, nullable=False, default=True)
    # Optional custom name/label for the invite
    name = Column(String(100), nullable=True)

    workspace = relationship("Workspace", back_populates="invites")
    role = relationship("WorkspaceRole", back_populates="invites")
    created_by = relationship("User", back_populates="created_invites")
    used_by_memberships = relationship(
        "WorkspaceMembership",
        back_populates="invited_by_invite",
        passive_deletes=True,
    )



class RefreshToken(Base, TimestampMixin):
    """
    Stores refresh tokens for user session management.
    Each row represents one device/session.
    """

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user = relationship("User", back_populates="refresh_tokens")
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    revoked_at = Column(TIMESTAMP(timezone=True), nullable=True)
    absolute_expiry = Column(TIMESTAMP(timezone=True), nullable=True)
    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.is_expired and self.revoked_at is None



class PersonalAccessToken(BaseModel, TimestampMixin):
    """
    Stores hashed Personal Access Tokens for programmatic API access.
    Plaintext tokens are shown once on creation and are never persisted.

    Scoped PATs (token_kind='agent_chat') bind to exactly one workspace
    and one vertical client. Client-supplied IDs are intersected with the
    token scope at runtime; the schema enforces a minimum scope for
    agent_chat tokens.
    """

    __tablename__ = "personal_access_tokens"

    __table_args__ = (
        CheckConstraint(
            "(token_kind != 'agent_chat') OR "
            "(workspace_id IS NOT NULL AND client_id IS NOT NULL AND scopes != '[]'::jsonb)",
            name="chk_pat_agent_chat_requires_scope",
        ),
        CheckConstraint(
            "(agent_id IS NULL) OR (client_id IS NOT NULL)",
            name="chk_pat_agent_id_requires_client_id",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user = relationship("User", back_populates="personal_access_tokens")
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    token_prefix = Column(String(16), nullable=False)
    label = Column(String, nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    last_used_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # PAT scope fields (Epic 18)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    client_id = Column(Text, nullable=True, index=True)
    agent_id = Column(Text, nullable=True, index=True)
    scopes = Column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    token_kind = Column(
        Text,
        nullable=False,
        default="legacy",
        server_default="legacy",
    )

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and datetime.now(UTC) >= self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.is_expired
