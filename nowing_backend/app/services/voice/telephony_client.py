"""Telephony client for LiveKit SIP Gateway and Room orchestration.

Story 38.1 / Invariant AD-122:
- Connects to LiveKit Server SDK to create audio rooms (call_<session_uuid>).
- Generates secure participant access tokens with Audio/WebRTC grants for Voice Workers.
- Dispatches SIP outbound calls to domestic carriers via LiveKit SIP Gateway.
- Handles failover routing across SIP trunk pools (e.g. Viettel, VNPT, FPT, CMC).
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import re
from typing import Any

import aiohttp
from livekit.api import (
    AccessToken,
    CreateRoomRequest,
    CreateSIPParticipantRequest,
    DeleteRoomRequest,
    ListRoomsRequest,
    LiveKitAPI,
    Room,
    RoomParticipantIdentity,
    SIPParticipantInfo,
    TwirpError,
    TwirpErrorCode,
    VideoGrants,
)

from app.config import (
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    LIVEKIT_URL,
    SIP_CALL_MAX_DURATION_SECONDS,
    SIP_OUTBOUND_GATEWAY_HOST,
    SIP_OUTBOUND_GATEWAY_PORT,
    SIP_RINGING_TIMEOUT_SECONDS,
    SIP_ROOM_PREFIX,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Telephony Domain Exceptions
# ---------------------------------------------------------------------------

class TelephonyError(Exception):
    """Base exception for telephony and voice SDR operations."""


class RoomCreationError(TelephonyError):
    """Raised when creating a LiveKit call room fails."""


class TokenGenerationError(TelephonyError):
    """Raised when generating a LiveKit participant token fails."""


class SIPDispatchError(TelephonyError):
    """Base exception for SIP outbound dispatch failures."""

    def __init__(
        self,
        message: str,
        phone_number: str | None = None,
        trunk_id: str | None = None,
        sip_code: int | None = None,
        attempted_trunks: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.phone_number = phone_number
        self.trunk_id = trunk_id
        self.sip_code = sip_code
        self.attempted_trunks = attempted_trunks or []


class SIPTrunkBusyError(SIPDispatchError):
    """Raised when carrier SIP trunk returns 486 Busy Here."""

    def __init__(
        self,
        message: str = "SIP trunk returned 486 Busy Here",
        phone_number: str | None = None,
        trunk_id: str | None = None,
        attempted_trunks: list[str] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            phone_number=phone_number,
            trunk_id=trunk_id,
            sip_code=486,
            attempted_trunks=attempted_trunks,
        )


class SIPServiceUnavailableError(SIPDispatchError):
    """Raised when carrier or SIP gateway returns 503 Service Unavailable."""

    def __init__(
        self,
        message: str = "SIP Gateway or trunk returned 503 Service Unavailable",
        phone_number: str | None = None,
        trunk_id: str | None = None,
        attempted_trunks: list[str] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            phone_number=phone_number,
            trunk_id=trunk_id,
            sip_code=503,
            attempted_trunks=attempted_trunks,
        )


class SIPCodecNotAcceptableError(SIPDispatchError):
    """Raised when remote peer returns 488 Not Acceptable Here (codec mismatch)."""

    def __init__(
        self,
        message: str = "SIP peer returned 488 Not Acceptable Here (unsupported audio codec)",
        phone_number: str | None = None,
        trunk_id: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            phone_number=phone_number,
            trunk_id=trunk_id,
            sip_code=488,
        )


class SIPCallNotFoundError(SIPDispatchError):
    """Raised when dialed number or trunk does not exist (404 Not Found)."""

    def __init__(
        self,
        message: str = "SIP peer returned 404 Not Found",
        phone_number: str | None = None,
        trunk_id: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            phone_number=phone_number,
            trunk_id=trunk_id,
            sip_code=404,
        )


class SIPTrunkFailoverError(SIPDispatchError):
    """Raised when all primary and fallback SIP trunks fail."""


# ---------------------------------------------------------------------------
# Telephony Client Implementation
# ---------------------------------------------------------------------------

class LiveKitTelephonyClient:
    """Async client orchestrating LiveKit rooms and SIP outbound dispatches."""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        sip_gateway_host: str | None = None,
        sip_gateway_port: int | None = None,
        api: LiveKitAPI | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.url = (url or LIVEKIT_URL or "").strip()
        self.api_key = (api_key or LIVEKIT_API_KEY or "").strip()
        self.api_secret = (api_secret or LIVEKIT_API_SECRET or "").strip()
        self.sip_gateway_host = sip_gateway_host or SIP_OUTBOUND_GATEWAY_HOST
        self.sip_gateway_port = sip_gateway_port or SIP_OUTBOUND_GATEWAY_PORT

        self._api: LiveKitAPI | None = api
        self._session: aiohttp.ClientSession | None = session
        self._owns_api: bool = api is None
        self._api_lock: asyncio.Lock = asyncio.Lock()

    async def _get_api(self) -> LiveKitAPI:
        """Lazily initialize LiveKitAPI inside an active event loop (async-safe)."""
        async with self._api_lock:
            if self._api is None:
                if not self.url or not self.api_key or not self.api_secret:
                    raise TelephonyError(
                        "LiveKit URL, API key, and API secret must be configured"
                    )
                self._api = LiveKitAPI(
                    url=self.url,
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    session=self._session,
                )
            return self._api

    @staticmethod
    def normalize_room_name(session_id: str) -> str:
        """Format room name with call_ prefix compliant with Invariant AD-122."""
        session_id_clean = session_id.strip()
        if not session_id_clean:
            raise ValueError("session_id must not be empty")
        if session_id_clean.startswith(SIP_ROOM_PREFIX):
            return session_id_clean
        return f"{SIP_ROOM_PREFIX}{session_id_clean}"

    @staticmethod
    def normalize_phone_number(phone_number: str) -> str:
        """Normalize phone number to standard clean format (E.164-safe)."""
        if not isinstance(phone_number, str):
            raise ValueError("phone_number must be a string")
        cleaned = re.sub(r"[\s\-\(\)\.]+", "", phone_number.strip())
        if not cleaned:
            raise ValueError("phone_number must not be empty")
        if not re.fullmatch(r"\+?\d{7,15}", cleaned):
            raise ValueError(
                f"phone_number '{cleaned}' is not a valid E.164 phone number"
            )
        return cleaned

    async def create_call_room(
        self,
        session_id: str,
        empty_timeout: int = 300,
        departure_timeout: int = 60,
        metadata: str | None = None,
    ) -> Room:
        """Create a LiveKit room designated for a telephony call session.

        Args:
            session_id: Unique session identifier or UUID.
            empty_timeout: Seconds before closing an empty room (default 300s).
            departure_timeout: Seconds before closing after participants leave.
            metadata: Custom JSON metadata attached to the room.

        Returns:
            Room descriptor object from LiveKit server.

        Raises:
            RoomCreationError: If creation fails or server rejects request.
        """
        room_name = self.normalize_room_name(session_id)
        api = await self._get_api()

        request = CreateRoomRequest(
            name=room_name,
            empty_timeout=empty_timeout,
            departure_timeout=departure_timeout,
            metadata=metadata or json.dumps({"session_id": session_id}),
        )

        try:
            logger.info("Creating LiveKit call room: %s", room_name)
            room = await api.room.create_room(request)
            logger.info("Successfully created LiveKit room: %s", room.name)
            return room
        except TwirpError as exc:
            logger.error("Twirp error creating room %s: %s", room_name, exc)
            raise RoomCreationError(
                f"LiveKit server error creating room {room_name}: {exc.message}"
            ) from exc
        except Exception as exc:
            logger.error("Unexpected error creating room %s: %s", room_name, exc)
            raise RoomCreationError(
                f"Failed to create LiveKit room {room_name}: {exc}"
            ) from exc

    def generate_participant_token(
        self,
        room_name: str,
        identity: str,
        name: str | None = None,
        metadata: str | None = None,
        ttl: int | datetime.timedelta = 3600,
        is_agent: bool = True,
        can_publish: bool = True,
        can_subscribe: bool = True,
        can_publish_data: bool = True,
    ) -> str:
        """Generate a signed JWT token granting access to a specific call room.

        Args:
            room_name: LiveKit room name (e.g. call_<uuid>).
            identity: Unique participant identifier (e.g. worker_0, agent_sdr).
            name: Human-readable participant display name.
            metadata: Custom metadata passed to room events.
            ttl: Token lifetime in seconds or as timedelta (default 1h).
            is_agent: Flag granting Voice Agent worker privileges.
            can_publish: Permission to publish audio tracks.
            can_subscribe: Permission to subscribe to audio tracks.
            can_publish_data: Permission to send DataTrack control messages.

        Returns:
            Signed JWT string.

        Raises:
            TokenGenerationError: If API credentials or inputs are invalid.
        """
        if not self.api_key or not self.api_secret:
            raise TokenGenerationError("API key and secret required for token generation")
        if not room_name or not identity:
            raise TokenGenerationError("room_name and identity must not be empty")
        if isinstance(ttl, (int, float)) and ttl <= 0:
            raise TokenGenerationError("ttl must be a positive number of seconds")

        token_ttl = (
            datetime.timedelta(seconds=ttl)
            if isinstance(ttl, (int, float))
            else ttl
        )

        try:
            token = (
                AccessToken(self.api_key, self.api_secret)
                .with_identity(identity)
                .with_ttl(token_ttl)
                .with_grants(
                    VideoGrants(
                        room_join=True,
                        room=room_name,
                        agent=is_agent,
                        can_publish=can_publish,
                        can_subscribe=can_subscribe,
                        can_publish_data=can_publish_data,
                    )
                )
            )
            if name:
                token = token.with_name(name)
            if metadata:
                token = token.with_metadata(metadata)

            jwt_str = token.to_jwt()
            logger.debug(
                "Generated participant token for %s in room %s",
                identity,
                room_name,
            )
            return jwt_str
        except Exception as exc:
            logger.error("Failed to generate participant token: %s", exc)
            raise TokenGenerationError(f"Token generation failed: {exc}") from exc

    async def dispatch_sip_outbound(
        self,
        phone_number: str,
        trunk_id: str,
        room_name: str,
        fallback_trunk_ids: list[str] | None = None,
        participant_identity: str | None = None,
        participant_name: str | None = None,
        dtmf: str | None = None,
        ringing_timeout: int | None = None,
        max_call_duration: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> SIPParticipantInfo:
        """Dispatch an outbound SIP call via LiveKit SIP Gateway with trunk failover.

        Args:
            phone_number: Destination phone number (E.164 format preferred).
            trunk_id: Primary SIP Trunk ID configured in LiveKit SIP Gateway.
            room_name: Target LiveKit room (call_<uuid>).
            fallback_trunk_ids: Optional ordered list of fallback SIP trunk IDs.
            participant_identity: Unique identity for the SIP participant.
            participant_name: Display name for the SIP participant.
            dtmf: DTMF digits to send upon answer.
            ringing_timeout: Timeout in seconds waiting for remote answer.
            max_call_duration: Hard ceiling duration in seconds (AD-126b: 175-180s).
            headers: Custom SIP headers forwarded in INVITE.

        Returns:
            SIPParticipantInfo containing participant_id and sip_call_id.

        Raises:
            SIPTrunkBusyError: If trunk returns 486 and all fallbacks fail.
            SIPServiceUnavailableError: If trunk/gateway returns 503.
            SIPCodecNotAcceptableError: If remote rejects codec (488).
            SIPCallNotFoundError: If remote number not found (404).
            SIPDispatchError: For general dispatch failures.
        """
        if not trunk_id or not trunk_id.strip():
            raise SIPDispatchError("trunk_id must not be empty")
        clean_phone = self.normalize_phone_number(phone_number)
        norm_room = self.normalize_room_name(room_name)
        effective_identity = participant_identity or f"sip_{clean_phone}"
        effective_name = participant_name or f"Tel {clean_phone}"
        effective_ringing_timeout = (
            ringing_timeout if ringing_timeout is not None else SIP_RINGING_TIMEOUT_SECONDS
        )
        effective_max_duration = (
            max_call_duration if max_call_duration is not None else SIP_CALL_MAX_DURATION_SECONDS
        )

        trunks_to_try = [trunk_id]
        if fallback_trunk_ids:
            for fb_id in fallback_trunk_ids:
                if fb_id and fb_id not in trunks_to_try:
                    trunks_to_try.append(fb_id)

        attempted_trunks: list[str] = []
        last_exception: Exception | None = None

        api = await self._get_api()

        for idx, current_trunk in enumerate(trunks_to_try):
            attempted_trunks.append(current_trunk)
            attempt_identity = (
                f"{effective_identity}_{idx}" if idx > 0 else effective_identity
            )
            request = CreateSIPParticipantRequest(
                sip_trunk_id=current_trunk,
                sip_call_to=clean_phone,
                room_name=norm_room,
                participant_identity=attempt_identity,
                participant_name=effective_name,
                dtmf=dtmf or "",
                ringing_timeout=datetime.timedelta(seconds=effective_ringing_timeout),
                max_call_duration=datetime.timedelta(seconds=effective_max_duration),
                headers=headers or {},
            )

            try:
                logger.info(
                    "Dispatching outbound SIP call: to=%s, trunk=%s, room=%s (attempt %d/%d)",
                    clean_phone,
                    current_trunk,
                    norm_room,
                    idx + 1,
                    len(trunks_to_try),
                )
                participant_info = await api.sip.create_sip_participant(request)
                logger.info(
                    "SIP outbound dispatch successful: participant_id=%s, call_id=%s, trunk=%s",
                    participant_info.participant_id,
                    participant_info.sip_call_id,
                    current_trunk,
                )
                return participant_info

            except TwirpError as exc:
                last_exception = exc
                err_code = exc.code
                err_status = getattr(exc, "status", None)
                err_msg = exc.message.lower()

                logger.warning(
                    "SIP dispatch failed on trunk %s: code=%s, status=%s, msg=%s",
                    current_trunk,
                    err_code,
                    err_status,
                    exc.message,
                )

                # Classify by SIP status code first (most reliable), then Twirp code.
                sip_status = err_status if isinstance(err_status, int) else None
                is_codec_error = sip_status == 488 or "codec" in err_msg
                is_not_found = sip_status == 404 or err_code == TwirpErrorCode.NOT_FOUND
                is_busy = (
                    sip_status == 486
                    or (sip_status is None and "486" in err_msg)
                    or "busy" in err_msg
                    or err_code == TwirpErrorCode.RESOURCE_EXHAUSTED
                )
                is_unavailable = (
                    sip_status == 503
                    or (sip_status is None and "503" in err_msg)
                    or "unavailable" in err_msg
                    or err_code in (TwirpErrorCode.UNAVAILABLE, TwirpErrorCode.DEADLINE_EXCEEDED)
                )

                # Codec mismatch and not-found take priority — never retry on fallback
                if is_codec_error:
                    raise SIPCodecNotAcceptableError(
                        message=f"SIP Codec mismatch on {current_trunk}: {exc.message}",
                        phone_number=clean_phone,
                        trunk_id=current_trunk,
                    ) from exc

                if is_not_found:
                    raise SIPCallNotFoundError(
                        message=f"Destination or trunk not found (404): {exc.message}",
                        phone_number=clean_phone,
                        trunk_id=current_trunk,
                    ) from exc

                if (is_busy or is_unavailable) and idx < len(trunks_to_try) - 1:
                    logger.info(
                        "Failover: Trunk %s busy/unavailable. Trying next fallback trunk: %s",
                        current_trunk,
                        trunks_to_try[idx + 1],
                    )
                    continue

                # Map to specific telephony error
                if is_busy:
                    raise SIPTrunkBusyError(
                        message=f"SIP Trunk {current_trunk} busy: {exc.message}",
                        phone_number=clean_phone,
                        trunk_id=current_trunk,
                        attempted_trunks=attempted_trunks,
                    ) from exc

                if is_unavailable:
                    raise SIPServiceUnavailableError(
                        message=f"SIP Trunk/Gateway {current_trunk} unavailable: {exc.message}",
                        phone_number=clean_phone,
                        trunk_id=current_trunk,
                        attempted_trunks=attempted_trunks,
                    ) from exc

                raise SIPDispatchError(
                    message=f"SIP dispatch error on trunk {current_trunk}: {exc.message}",
                    phone_number=clean_phone,
                    trunk_id=current_trunk,
                    attempted_trunks=attempted_trunks,
                ) from exc

            except (aiohttp.ClientError, TimeoutError) as exc:
                last_exception = exc
                logger.warning(
                    "Network error on trunk %s: %s",
                    current_trunk,
                    exc,
                )
                if idx < len(trunks_to_try) - 1:
                    logger.info(
                        "Failover on network failure to next fallback trunk: %s",
                        trunks_to_try[idx + 1],
                    )
                    continue
                raise SIPServiceUnavailableError(
                    message=f"Network failure connecting to SIP gateway: {exc}",
                    phone_number=clean_phone,
                    trunk_id=current_trunk,
                    attempted_trunks=attempted_trunks,
                ) from exc

            except Exception as exc:
                last_exception = exc
                logger.error("Unexpected error dispatching SIP call: %s", exc)
                raise SIPDispatchError(
                    message=f"Unexpected error dispatching SIP call: {exc}",
                    phone_number=clean_phone,
                    trunk_id=current_trunk,
                    attempted_trunks=attempted_trunks,
                ) from exc

        # Unreachable: every branch inside the loop either returns or raises.
        # Kept as a defensive fallback if the loop ever exits without raising.
        raise SIPTrunkFailoverError(
            message=f"All {len(attempted_trunks)} attempted SIP trunks failed: {last_exception}",
            phone_number=clean_phone,
            trunk_id=trunk_id,
            attempted_trunks=attempted_trunks,
        )


    # ---------------------------------------------------------------------------
    # Call Lifecycle Management
    # ---------------------------------------------------------------------------

    async def end_call(
        self,
        room_name: str,
        participant_identity: str | None = None,
    ) -> None:
        """Terminate an active call by removing the SIP participant or closing the room.

        When ``participant_identity`` is supplied, only that SIP leg is removed
        (e.g. hang up a single call leg while keeping the room open for logging).
        When omitted, the entire room is deleted which disconnects all
        participants and triggers room-cleanup workflows in LiveKit.

        Args:
            room_name: LiveKit room name (``call_<uuid>``). Used verbatim —
                normalization belongs to ``session_id`` inputs at
                :meth:`create_call_room`, not to a name already resolved.
            participant_identity: SIP participant identity to remove, or None
                to delete the whole room.

        Raises:
            TelephonyError: If the LiveKit API call fails — including
                NOT_FOUND, so an escalation can't report success while
                the room stays connected.
        """
        api = await self._get_api()

        if participant_identity:
            try:
                logger.info(
                    "Removing SIP participant %s from room %s",
                    participant_identity,
                    room_name,
                )
                await api.room.remove_participant(
                    RoomParticipantIdentity(
                        room=room_name,
                        identity=participant_identity,
                    )
                )
                logger.info(
                    "Participant %s removed from room %s",
                    participant_identity,
                    room_name,
                )
            except TwirpError as exc:
                if exc.code == TwirpErrorCode.NOT_FOUND:
                    logger.warning(
                        "Participant %s not found in room %s",
                        participant_identity,
                        room_name,
                    )
                raise TelephonyError(
                    f"Failed to remove participant {participant_identity} "
                    f"from room {room_name}: {exc.message}"
                ) from exc
        else:
            try:
                logger.info("Deleting room %s (all participants will disconnect)", room_name)
                await api.room.delete_room(DeleteRoomRequest(room=room_name))
                logger.info("Room %s deleted", room_name)
            except TwirpError as exc:
                if exc.code == TwirpErrorCode.NOT_FOUND:
                    logger.warning("Room %s not found — nothing deleted", room_name)
                raise TelephonyError(
                    f"Failed to delete room {room_name}: {exc.message}"
                ) from exc

    async def delete_room(self, room_name: str) -> None:
        """Delete a LiveKit room, disconnecting all participants.

        Convenience wrapper around :meth:`end_call` with no participant filter.
        """
        await self.end_call(room_name=room_name, participant_identity=None)

    async def list_active_rooms(self, name_prefix: str | None = None) -> list[str]:
        """Return names of currently active rooms, optionally filtered by prefix.

        Args:
            name_prefix: Filter results to rooms whose name starts with this
                string (e.g. ``"call_"``). Defaults to ``SIP_ROOM_PREFIX``.

        Returns:
            List of active room names.

        Raises:
            TelephonyError: If the LiveKit API call fails.
        """
        api = await self._get_api()
        prefix = name_prefix if name_prefix is not None else SIP_ROOM_PREFIX
        try:
            response = await api.room.list_rooms(ListRoomsRequest())
            names = [r.name for r in response.rooms if r.name.startswith(prefix)]
            logger.debug("Active rooms matching '%s': %s", prefix, names)
            return names
        except TwirpError as exc:
            raise TelephonyError(
                f"Failed to list rooms: {exc.message}"
            ) from exc

    async def aclose(self) -> None:
        """Close underlying LiveKitAPI resources."""
        if self._owns_api and self._api is not None:
            try:
                await self._api.aclose()
            except Exception as exc:
                logger.debug("Error closing LiveKitAPI: %s", exc)
            finally:
                self._api = None

    async def close(self) -> None:
        """Alias for aclose()."""
        await self.aclose()

    async def __aenter__(self) -> LiveKitTelephonyClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()
