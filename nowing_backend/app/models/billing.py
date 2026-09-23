"""Models for the billing domain."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    Enum as SQLAlchemyEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, BaseModel, TimestampMixin
from app.db.enums import CreditPurchaseStatus, IncentiveTaskType, PagePurchaseStatus


class TokenUsage(BaseModel, TimestampMixin):
    """
    Tracks LLM token consumption per assistant turn.

    One row per usage event. For chat, linked to a specific message via message_id.
    The usage_type column enables future extension to track non-chat usage
    (indexing, image generation, podcasts, etc.) without schema changes.
    """

    __tablename__ = "token_usage"

    # Partial unique index on (message_id) where message_id IS NOT NULL.
    # Mirrors alembic migration 142. Lets the streaming agent's
    # ``finalize_assistant_turn`` and the legacy frontend ``append_message``
    # recovery branch both use ``INSERT ... ON CONFLICT DO NOTHING`` without
    # racing on a SELECT-then-INSERT window. Partial so non-chat usage rows
    # (indexing, image generation, podcasts) — which keep ``message_id`` NULL
    # because there is no per-message anchor — are unaffected.
    __table_args__ = (
        Index(
            "uq_token_usage_message_id",
            "message_id",
            unique=True,
            postgresql_where=text("message_id IS NOT NULL"),
        ),
        Index(
            "ix_token_usage_deep_research_resolved_mode_created_at",
            "usage_type",
            "resolved_mode",
            "created_at",
            postgresql_where=text(
                "usage_type = 'deep_research' AND resolved_mode IS NOT NULL"
            ),
        ),
        # AC-18.7: daily cost rollups by workspace + client.
        Index(
            "ix_token_usage_workspace_client_created_at",
            "workspace_id",
            "client_id",
            "created_at",
        ),
    )

    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    cost_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    model_breakdown = Column(JSONB, nullable=True)
    call_details = Column(JSONB, nullable=True)
    resolved_mode = Column(String(50), nullable=True)
    mode_requested = Column(String(50), nullable=True)
    e2e_ms = Column(Integer, nullable=True)
    ttfb_ms = Column(Integer, nullable=True)

    usage_type = Column(String(50), nullable=False, default="chat", index=True)

    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    message_id = Column(
        Integer,
        ForeignKey("new_chat_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(Text, nullable=True, index=True)
    external_metadata = Column(JSONB, nullable=True, default=dict)
    run_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Relationships
    thread = relationship("NewChatThread", back_populates="token_usages")
    message = relationship("NewChatMessage", back_populates="token_usage")
    workspace = relationship("Workspace")
    user = relationship("User")


class UserIncentiveTask(BaseModel, TimestampMixin):
    """
    Tracks completed incentive tasks for users.
    Each user can only complete each task type once.
    When a task is completed, the user's credit_micros_balance is increased.
    """

    __tablename__ = "user_incentive_tasks"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "task_type",
            name="uq_user_incentive_task",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_type = Column(SQLAlchemyEnum(IncentiveTaskType), nullable=False, index=True)
    # Credit reward granted in USD micro-units (1_000_000 == $1.00).
    credit_micros_awarded = Column(BigInteger, nullable=False)
    completed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    user = relationship("User", back_populates="incentive_tasks")


class PagePurchase(Base, TimestampMixin):
    """Tracks Stripe checkout sessions used to grant additional page credits."""

    __tablename__ = "page_purchases"
    __allow_unmapped__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_checkout_session_id = Column(
        String(255), nullable=False, unique=True, index=True
    )
    stripe_payment_intent_id = Column(String(255), nullable=True, index=True)
    quantity = Column(Integer, nullable=False)
    pages_granted = Column(Integer, nullable=False)
    amount_total = Column(Integer, nullable=True)
    currency = Column(String(10), nullable=True)
    status = Column(
        SQLAlchemyEnum(PagePurchaseStatus),
        nullable=False,
        default=PagePurchaseStatus.PENDING,
        server_default=text("'PENDING'::pagepurchasestatus"),
        index=True,
    )
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    user = relationship("User", back_populates="page_purchases")


class CreditPurchase(Base, TimestampMixin):
    """Tracks Stripe checkout sessions used to grant credit (USD micro-units).

    Renamed from ``premium_token_purchases`` in migration 156 as part of the
    unified-credits wallet. ``credit_micros_granted`` stores the USD-micro
    amount added to ``user.credit_micros_balance`` on fulfillment.

    ``source`` distinguishes a user-initiated checkout from an automatic
    off-session top-up (auto-reload), added in the auto-reload migration.
    """

    __tablename__ = "credit_purchases"
    __allow_unmapped__ = True
    __table_args__ = (
        Index(
            "ix_credit_purchases_status_completed_at",
            "status",
            "completed_at",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_checkout_session_id = Column(
        String(255), nullable=False, unique=True, index=True
    )
    stripe_payment_intent_id = Column(String(255), nullable=True, index=True)
    quantity = Column(Integer, nullable=False)
    credit_micros_granted = Column(BigInteger, nullable=False)
    amount_total = Column(Integer, nullable=True)
    currency = Column(String(10), nullable=True)
    source = Column(
        String(20), nullable=False, default="checkout", server_default="checkout"
    )
    status = Column(
        SQLAlchemyEnum(CreditPurchaseStatus),
        nullable=False,
        default=CreditPurchaseStatus.PENDING,
        index=True,
    )
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    user = relationship("User", back_populates="credit_purchases")


class BillingEvent(Base, TimestampMixin):
    """Canonical ledger for non-LLM business events (e.g. signal scans)."""

    __tablename__ = "billing_events"

    __table_args__ = (
        Index(
            "ix_billing_events_event_lookup",
            "event_entity_type",
            "event_type",
            "event_id",
        ),
        Index(
            "ix_billing_events_outcome_unique",
            "event_id",
            unique=True,
            postgresql_where=text("event_entity_type = 'outcome_event'"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(CITEXT, nullable=True, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_entity_type = Column(String(50), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), nullable=False)
    cost_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    currency = Column(String(3), nullable=False, default="USD", server_default="USD")
    cost_basis = Column(
        String(20), nullable=False, default="estimated", server_default="estimated"
    )

    workspace = relationship("Workspace")
    user = relationship("User")


class PricingPlan(Base, TimestampMixin):
    """Workspace pricing plan configuration (seat, outcome, hybrid) (Story 21.7 / AD-42)."""

    __tablename__ = "pricing_plans"

    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_pricing_plans_workspace_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(CITEXT, nullable=True, index=True)
    plan_type = Column(
        String(50), nullable=False, default="outcome", server_default="outcome"
    )  # seat | outcome | hybrid
    seat_price = Column(BigInteger, nullable=True)  # micros per seat
    outcome_rates_json = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    billing_period = Column(
        String(20), nullable=True, default="monthly", server_default="monthly"
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")

    workspace = relationship("Workspace")


class PromoCode(Base, TimestampMixin):
    """Gift / promotional codes that grant credits to user wallets (Story 21.7 / AC-5)."""

    __tablename__ = "promo_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), nullable=False, unique=True, index=True)
    credit_micros_granted = Column(BigInteger, nullable=False)
    max_uses = Column(Integer, nullable=True)
    uses_count = Column(Integer, nullable=False, default=0, server_default="0")
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )


class PromoCodeRedemption(Base, TimestampMixin):
    """Tracks which users have redeemed which promo codes (Story 21.7 / AC-5)."""

    __tablename__ = "promo_code_redemptions"

    __table_args__ = (
        UniqueConstraint(
            "user_id", "promo_code_id", name="uq_promo_code_redemption_user_code"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    promo_code_id = Column(
        UUID(as_uuid=True),
        ForeignKey("promo_codes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    credit_micros_granted = Column(BigInteger, nullable=False)
    redeemed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    user = relationship("User")
    promo_code = relationship("PromoCode")


class AffiliatePartner(Base, TimestampMixin):
    """Affiliate Partner account for Nowing referral program (Story 21.18 / Story 23.3 / AD-44)."""

    __tablename__ = "affiliate_partners"
    __table_args__ = (
        UniqueConstraint("referral_code", name="uq_affiliate_partners_referral_code"),
        Index("ix_affiliate_partners_user_id", "user_id"),
        Index("ix_affiliate_partners_referral_code", "referral_code"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    referral_code = Column(CITEXT, nullable=False)
    partner_type = Column(
        String(50), nullable=False, default="agency", server_default=text("'agency'")
    )
    status = Column(
        String(30), nullable=False, default="active", server_default=text("'active'")
    )
    commission_rate = Column(Float, nullable=False, default=0.15, server_default="0.15")
    balance_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    hold_balance_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    total_earned_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    total_paid_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    payout_method = Column(
        String(30), nullable=False, default="vietqr", server_default=text("'vietqr'")
    )
    payout_details = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    user = relationship("User")
    referrals = relationship(
        "PartnerReferral", back_populates="partner", cascade="all, delete-orphan"
    )
    commissions = relationship(
        "PartnerCommission", back_populates="partner", cascade="all, delete-orphan"
    )
    payouts = relationship(
        "PartnerPayout", back_populates="partner", cascade="all, delete-orphan"
    )

    @property
    def available_balance_micros(self) -> int:
        return self.balance_micros

    @available_balance_micros.setter
    def available_balance_micros(self, value: int) -> None:
        self.balance_micros = value


class PartnerReferral(Base, TimestampMixin):
    """Referred user attribution (Story 21.18)."""

    __tablename__ = "partner_referrals"
    __table_args__ = (
        UniqueConstraint("referred_user_id", name="uq_partner_referrals_referred_user"),
        Index("ix_partner_referrals_partner_id", "partner_id"),
        Index("ix_partner_referrals_referred_user_id", "referred_user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("affiliate_partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    referred_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    attribution_source = Column(
        String(100),
        nullable=True,
        default="direct_ref",
        server_default=text("'direct_ref'"),
    )
    landing_page = Column(String(255), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    partner = relationship("AffiliatePartner", back_populates="referrals")
    referred_user = relationship("User")
    commissions = relationship(
        "PartnerCommission", back_populates="referral", cascade="all, delete-orphan"
    )


class PartnerCommission(Base, TimestampMixin):
    """Commission payout ledger event from user credit purchase (Story 21.18)."""

    __tablename__ = "partner_commissions"
    __table_args__ = (
        Index("ix_partner_commissions_partner_id", "partner_id"),
        Index("ix_partner_commissions_referral_id", "referral_id"),
        Index("ix_partner_commissions_credit_purchase_id", "credit_purchase_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("affiliate_partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    referral_id = Column(
        UUID(as_uuid=True),
        ForeignKey("partner_referrals.id", ondelete="CASCADE"),
        nullable=False,
    )
    credit_purchase_id = Column(
        UUID(as_uuid=True),
        ForeignKey("credit_purchases.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_amount_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    commission_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    commission_rate = Column(Float, nullable=False, default=0.15, server_default="0.15")
    currency = Column(
        String(10), nullable=False, default="USD", server_default=text("'USD'")
    )
    status = Column(
        String(20), nullable=False, default="settled", server_default=text("'settled'")
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    partner = relationship("AffiliatePartner", back_populates="commissions")
    referral = relationship("PartnerReferral", back_populates="commissions")


class PartnerPayout(Base, TimestampMixin):
    """Partner payout request / transaction record (Story 21.18)."""

    __tablename__ = "partner_payouts"
    __table_args__ = (
        Index("ix_partner_payouts_partner_id", "partner_id"),
        Index("ix_partner_payouts_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("affiliate_partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount_micros = Column(BigInteger, nullable=False)
    amount_vnd = Column(BigInteger, nullable=False, default=0, server_default="0")
    tax_deducted_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    net_amount_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    tax_code = Column(String(50), nullable=True)
    payout_method = Column(
        String(30), nullable=False, default="vietqr", server_default=text("'vietqr'")
    )
    payout_details = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    status = Column(
        String(20), nullable=False, default="pending", server_default=text("'pending'")
    )
    tx_reference = Column(String(100), nullable=True)
    napas_ref = Column(String(100), nullable=True)
    hmac_audit_hash = Column(String(128), nullable=True)
    requested_at = Column(TIMESTAMP(timezone=True), nullable=True)
    processed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    partner = relationship("AffiliatePartner", back_populates="payouts")


class AuditEvent(BaseModel, TimestampMixin):
    """Immutable dual-principal audit logging in audit_events."""

    __tablename__ = "audit_events"

    action = Column(String(100), nullable=False, index=True)
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subject_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ticket_ref = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    diff_payload = Column(JSONB, nullable=True)


class CreditTransaction(Base, TimestampMixin):
    """Immutable ledger for manual workspace credit adjustments."""

    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_admin_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id"),
        nullable=False,
        index=True,
    )
    direction = Column(String(10), nullable=False)
    amount_micros = Column(BigInteger, nullable=False)
    reason = Column(Text, nullable=False)
    ticket_ref = Column(Text, nullable=False)
    idempotency_key = Column(String(64), nullable=False, unique=True, index=True)
