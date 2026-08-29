"""Shared Contact Unlock Service (Story 26.6 / Story 26.5 / 920ru7).

Used by REST route (POST .../contacts/{contact_id}/unlock) and Telegram interactive checkpoint bot.
Handles DNC gating, per-channel wallet debit (1,500 micros per channel), PII decryption,
audit logging, and idempotency.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid5

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import Lead, VerifiedContact
from app.lead_intelligence.dnc.service import DncComplianceService
from app.services import wallet_credit
from app.services.billing_event_service import (
    BillingEventService,
    _list_billing_events,
)
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

logger = logging.getLogger(__name__)

CHANNEL_COST_MICROS = 1_500


class ContactUnlockResult(BaseModel):
    """Result of unlocking a verified contact or one of its channels."""

    contact_id: UUID
    is_unlocked: bool
    cost_micros: int
    channel: str | None = None
    unlocked_channels: list[str] = []
    name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    external_chat_ids: dict[str, str] | None = None


class ContactUnlockService:
    """Service encapsulating business rules for per-channel verified contact unlock."""

    def __init__(
        self,
        encryption: VerifiedContactEncryption | None = None,
        dnc_service: DncComplianceService | None = None,
        billing_event_service: BillingEventService | None = None,
    ) -> None:
        self.enc = encryption or VerifiedContactEncryption()
        self.dnc = dnc_service or DncComplianceService(secret_key=config.SECRET_KEY)
        self.billing = billing_event_service or BillingEventService()

    def decrypt_field(self, value: str | None) -> str | None:
        if not value:
            return None
        if self.enc.is_encrypted(value):
            try:
                return self.enc.decrypt(value)
            except Exception:
                return None
        try:
            decrypted = self.enc.decrypt(value)
            if decrypted is not None:
                return decrypted
        except Exception:
            pass
        return value

    def _decrypted(
        self, contact: VerifiedContact
    ) -> dict[str, str | dict[str, str] | None]:
        """Return a dict of decrypted contact fields."""
        external: dict[str, str] = {}
        raw_external = getattr(contact, "external_chat_ids", None) or {}
        if isinstance(raw_external, dict):
            for channel, enc_value in raw_external.items():
                if not enc_value or not isinstance(enc_value, str):
                    continue
                plain = self.decrypt_field(enc_value)
                if plain:
                    external[channel] = plain
        return {
            "name": self.decrypt_field(contact.name),
            "title": self.decrypt_field(contact.title),
            "email": self.decrypt_field(contact.email),
            "phone": self.decrypt_field(contact.phone),
            "external_chat_ids": external,
        }

    def _available_channels(self, contact: VerifiedContact) -> list[str]:
        """Return the channels this contact can unlock."""
        decrypted = self._decrypted(contact)
        channels: list[str] = []
        if decrypted.get("phone"):
            channels.append("phone")
        if decrypted.get("email"):
            channels.append("email")
        external = decrypted.get("external_chat_ids")
        if isinstance(external, dict):
            for key in external:
                if key and external[key]:
                    channels.append(key)
        return channels

    def _current_unlocked_channels(self, contact: VerifiedContact) -> list[str]:
        """Return channels that are already unlocked for this contact."""
        raw = getattr(contact, "unlocked_channels", None)
        if not raw:
            return []
        if isinstance(raw, list):
            return [str(c) for c in raw]
        return []

    def _is_channel_unlocked(self, contact: VerifiedContact, channel: str) -> bool:
        """Check whether a specific channel is unlocked."""
        if contact.is_unlocked and not self._current_unlocked_channels(contact):
            # Legacy whole-contact unlock: all channels visible.
            return True
        return channel in self._current_unlocked_channels(contact)

    def _channel_value(self, contact: VerifiedContact, channel: str) -> str | None:
        """Return the decrypted value for a single channel."""
        decrypted = self._decrypted(contact)
        if channel == "phone":
            return decrypted.get("phone") or None
        if channel == "email":
            return decrypted.get("email") or None
        external = decrypted.get("external_chat_ids")
        if isinstance(external, dict):
            return external.get(channel)
        return None

    def _channel_billing_id(self, contact: VerifiedContact, channel: str) -> UUID:
        """Deterministic per-channel billing identity.

        Using uuid5 means the same (contact, channel) always maps to the same
        BillingEvent ``event_id``, so retries are idempotent and relocks can
        locate the original unlock.
        """
        return uuid5(contact.id, f"channel:{channel}")

    def _build_result(
        self,
        contact: VerifiedContact,
        channel: str | None,
        cost_micros: int,
    ) -> ContactUnlockResult:
        """Build a response for the requested channel (or all channels when None)."""
        decrypted = self._decrypted(contact)
        unlocked = self._current_unlocked_channels(contact)
        if channel:
            external = {}
            phone = decrypted.get("phone") if channel == "phone" else None
            email = decrypted.get("email") if channel == "email" else None
            raw_external = decrypted.get("external_chat_ids")
            if (
                isinstance(raw_external, dict)
                and channel != "phone"
                and channel != "email"
            ):
                value = raw_external.get(channel)
                if value:
                    external[channel] = value
            return ContactUnlockResult(
                contact_id=contact.id,
                is_unlocked=contact.is_unlocked,
                cost_micros=cost_micros,
                channel=channel,
                unlocked_channels=unlocked,
                name=decrypted.get("name") or None,
                title=decrypted.get("title") or None,
                email=email,
                phone=phone,
                external_chat_ids=external if external else None,
            )

        return ContactUnlockResult(
            contact_id=contact.id,
            is_unlocked=contact.is_unlocked,
            cost_micros=cost_micros,
            channel=None,
            unlocked_channels=unlocked,
            name=decrypted.get("name") or None,
            title=decrypted.get("title") or None,
            email=decrypted.get("email") or None,
            phone=decrypted.get("phone") or None,
            external_chat_ids=decrypted.get("external_chat_ids") or None,
        )

    async def _bill_channel(
        self,
        session: AsyncSession,
        workspace_id: int,
        contact: VerifiedContact,
        channel: str,
        user_id: UUID,
    ) -> int:
        """Bill one channel unlock if not already billed. Returns the cost charged."""
        billing_id = self._channel_billing_id(contact, channel)
        existing = await _list_billing_events(
            session,
            event_entity_type="verified_contact",
            event_type="contact_unlock",
            event_id=billing_id,
            workspace_id=workspace_id,
        )
        if existing:
            return 0

        try:
            billing_event = await self.billing.record_contact_unlock(
                session,
                verified_contact_id=billing_id,
                workspace_id=workspace_id,
                client_id=None,
                user_id=user_id,
                cost_micros=CHANNEL_COST_MICROS,
            )
        except wallet_credit.InsufficientCreditsError as exc:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Insufficient credits to unlock {channel}.",
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Billing validation failed.",
            ) from exc
        except Exception as exc:
            logger.exception(
                "Failed to bill unlock for contact %s channel %s: %s",
                contact.id,
                channel,
                exc,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to unlock contact.",
            ) from exc

        return (
            getattr(billing_event, "cost_micros", CHANNEL_COST_MICROS)
            or CHANNEL_COST_MICROS
        )

    def _add_audit_log(
        self,
        contact: VerifiedContact,
        workspace_id: int,
        user_id: UUID,
        access_type: str,
        ip_address: str | None,
        reason: str,
        channel: str | None = None,
    ) -> None:
        existing_logs = list(contact.pii_access_audit_logs or [])
        contact.pii_access_audit_logs = [
            *existing_logs,
            {
                "user_id": str(user_id),
                "workspace_id": workspace_id,
                "lead_id": str(contact.lead_id),
                "contact_id": str(contact.id),
                "access_type": access_type,
                "channel": channel,
                "timestamp": datetime.now(UTC).isoformat(),
                "ip_address": ip_address,
                "reason": reason,
            },
        ]

    async def unlock_contact(
        self,
        session: AsyncSession,
        workspace_id: int,
        contact: VerifiedContact,
        user_id: UUID,
        *,
        channel: str | None = None,
        lead: Lead | None = None,
        ip_address: str | None = None,
        reason: str = "contact_unlock",
    ) -> ContactUnlockResult:
        """Unlock a contact or one of its channels."""
        if not contact.is_valid:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Contact is marked invalid and cannot be unlocked.",
            )
        if contact.consent_status == "withdrawn":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Contact consent has been withdrawn and cannot be unlocked.",
            )

        # Fail-closed DNC check (uses primary phone/email; external handles are not DNC-gated)
        decrypted_phone = self.decrypt_field(contact.phone)
        decrypted_email = self.decrypt_field(contact.email)
        domain = getattr(lead, "domain", None) if lead else None

        dnc_result = await self.dnc.is_blocked(
            workspace_id=workspace_id,
            phone=decrypted_phone,
            email=decrypted_email,
            domain=domain,
            session=session,
        )
        if dnc_result.is_blocked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Contact is blocked by DNC: {dnc_result.reason}",
            )

        available = self._available_channels(contact)
        if not available:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Contact has no unlockable channels.",
            )

        if channel and channel not in available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid channel '{channel}'. Available: {', '.join(available)}.",
            )

        # Idempotency: already unlocked for the requested scope.
        if channel:
            if self._is_channel_unlocked(contact, channel):
                return self._build_result(contact, channel, 0)
        else:
            all_unlocked = all(self._is_channel_unlocked(contact, c) for c in available)
            if all_unlocked:
                return self._build_result(contact, None, 0)

        # Legacy whole-contact unlock: a single 1500 micros charge unlocks all
        # channels. This path is used by tests, Telegram, and older callers.
        if (
            not channel
            and not contact.is_unlocked
            and not self._current_unlocked_channels(contact)
        ):
            try:
                billing_event = await self.billing.record_contact_unlock(
                    session,
                    verified_contact_id=contact.id,
                    workspace_id=workspace_id,
                    client_id=None,
                    user_id=user_id,
                    cost_micros=CHANNEL_COST_MICROS,
                )
            except wallet_credit.InsufficientCreditsError as exc:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail="Insufficient credits to unlock contact.",
                ) from exc
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Billing validation failed.",
                ) from exc
            except Exception as exc:
                logger.exception(
                    "Failed to bill unlock for contact %s: %s", contact.id, exc
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to unlock contact.",
                ) from exc

            contact.is_unlocked = True
            contact.unlocked_channels = available
            self._add_audit_log(
                contact,
                workspace_id,
                user_id,
                "unlock",
                ip_address,
                reason,
                channel=None,
            )
            return self._build_result(
                contact,
                None,
                getattr(billing_event, "cost_micros", CHANNEL_COST_MICROS)
                or CHANNEL_COST_MICROS,
            )

        # Bill and unlock each channel that is not yet unlocked.
        channels_to_unlock = [channel] if channel else available
        total_cost = 0
        newly_unlocked: list[str] = []
        for ch in channels_to_unlock:
            if self._is_channel_unlocked(contact, ch):
                continue
            cost = await self._bill_channel(session, workspace_id, contact, ch, user_id)
            total_cost += cost
            newly_unlocked.append(ch)

        if newly_unlocked:
            existing = set(self._current_unlocked_channels(contact))
            existing.update(newly_unlocked)
            contact.unlocked_channels = sorted(existing)
            contact.is_unlocked = True
            self._add_audit_log(
                contact,
                workspace_id,
                user_id,
                "unlock",
                ip_address,
                reason,
                channel=channel or ", ".join(newly_unlocked),
            )

        return self._build_result(contact, channel, total_cost)

    async def relock_contact(
        self,
        session: AsyncSession,
        workspace_id: int,
        contact: VerifiedContact,
        user_id: UUID,
        *,
        channel: str | None = None,
        ip_address: str | None = None,
        reason: str = "accidental_unlock",
    ) -> ContactUnlockResult:
        """Relock a contact or a single channel and refund the unlock cost.

        This is the 60-second accidental-undo path. Per-channel relock refunds
        the per-channel billing event.
        """
        if not contact.is_unlocked:
            return self._build_result(contact, channel, 0)

        available = self._available_channels(contact)
        unlocked = self._current_unlocked_channels(contact)

        if channel and channel not in available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid channel '{channel}'. Available: {', '.join(available)}.",
            )

        # Legacy whole-contact relock: refund the single legacy unlock event.
        if not channel and contact.is_unlocked and not unlocked:
            try:
                await self.billing.record_contact_relock(
                    session,
                    verified_contact_id=contact.id,
                    workspace_id=workspace_id,
                    client_id=None,
                    user_id=user_id,
                    cost_micros=CHANNEL_COST_MICROS,
                )
            except ValueError as exc:
                detail = str(exc).lower()
                if (
                    "relock window expired" in detail
                    or "relock budget exhausted" in detail
                ):
                    raise
                # Missing original event / already refunded: treat as idempotent.
                logger.warning(
                    "Failed to relock legacy contact %s: %s", contact.id, exc
                )
            except Exception as exc:
                logger.exception(
                    "Failed to relock legacy contact %s: %s", contact.id, exc
                )
                return self._build_result(contact, None, 0)

            contact.is_unlocked = False
            contact.unlocked_channels = []
            self._add_audit_log(
                contact,
                workspace_id,
                user_id,
                "relock",
                ip_address,
                reason,
                channel=None,
            )
            return self._build_result(contact, None, 0)

        channels_to_relock = [channel] if channel else unlocked
        total_refund = 0
        relocked_channels: list[str] = []

        for ch in channels_to_relock:
            if not self._is_channel_unlocked(contact, ch):
                continue
            billing_id = self._channel_billing_id(contact, ch)
            try:
                await self.billing.record_contact_relock(
                    session,
                    verified_contact_id=billing_id,
                    workspace_id=workspace_id,
                    client_id=None,
                    user_id=user_id,
                    cost_micros=CHANNEL_COST_MICROS,
                )
                total_refund += CHANNEL_COST_MICROS
                relocked_channels.append(ch)
            except ValueError as exc:
                detail = str(exc).lower()
                if (
                    "relock window expired" in detail
                    or "relock budget exhausted" in detail
                ):
                    raise
                # Missing original event / already refunded: still remove the channel.
                relocked_channels.append(ch)
            except Exception:
                # Ignore relock failures for individual channels; the contact
                # is re-locked below and the audit log records the attempt.
                pass

        if relocked_channels:
            remaining = set(self._current_unlocked_channels(contact)) - set(
                relocked_channels
            )
            contact.unlocked_channels = sorted(remaining)
            contact.is_unlocked = bool(remaining)
            self._add_audit_log(
                contact,
                workspace_id,
                user_id,
                "relock",
                ip_address,
                reason,
                channel=channel or ", ".join(relocked_channels),
            )

        return self._build_result(contact, channel, -total_refund)
