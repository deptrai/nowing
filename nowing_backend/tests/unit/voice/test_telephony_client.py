"""Unit tests for LiveKitTelephonyClient (Story 38.1 / Invariant AD-122).

Hermetic tests verifying:
- LiveKit room creation with call_<session_uuid> naming convention.
- Participant token generation with WebRTC audio/agent grants.
- SIP outbound call dispatching with carrier failover routing (486/503).
- Telecom error code mapping (486 Busy, 503 Unavailable, 488 Codec, 404 Not Found).
- Lifecycle & async context manager resource cleanup.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import jwt
import pytest
from livekit.api import (
    LiveKitAPI,
    Room,
    SIPParticipantInfo,
    TwirpError,
    TwirpErrorCode,
)

from app.services.voice.telephony_client import (
    LiveKitTelephonyClient,
    RoomCreationError,
    SIPCallNotFoundError,
    SIPCodecNotAcceptableError,
    SIPDispatchError,
    SIPServiceUnavailableError,
    SIPTrunkBusyError,
    TelephonyError,
    TokenGenerationError,
)

TEST_API_KEY = "API_KEY_MOCK_32_BYTES_LONG_00001"
TEST_API_SECRET = "API_SECRET_MOCK_32_BYTES_LONG_0001"
TEST_URL = "http://mock-livekit:7880"


@pytest.fixture
def mock_livekit_api():
    """Create a fully mocked LiveKitAPI instance."""
    api = MagicMock(spec=LiveKitAPI)
    api.room = MagicMock()
    api.room.create_room = AsyncMock()
    api.sip = MagicMock()
    api.sip.create_sip_participant = AsyncMock()
    api.aclose = AsyncMock()
    return api


@pytest.fixture
def telephony_client(mock_livekit_api):
    """Fixture providing LiveKitTelephonyClient injected with mock API."""
    return LiveKitTelephonyClient(
        url=TEST_URL,
        api_key=TEST_API_KEY,
        api_secret=TEST_API_SECRET,
        api=mock_livekit_api,
    )


# ---------------------------------------------------------------------------
# Room Creation Tests (call_<uuid> convention)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRoomCreation:
    """Tests for LiveKit call room creation."""

    @pytest.mark.asyncio
    async def test_create_call_room_success(self, telephony_client, mock_livekit_api):
        """Room creation prepends call_ prefix and returns Room descriptor."""
        expected_room = Room(name="call_sess-uuid-1234", sid="RM_123")
        mock_livekit_api.room.create_room.return_value = expected_room

        room = await telephony_client.create_call_room("sess-uuid-1234")

        assert room.name == "call_sess-uuid-1234"
        mock_livekit_api.room.create_room.assert_awaited_once()
        req = mock_livekit_api.room.create_room.call_args[0][0]
        assert req.name == "call_sess-uuid-1234"
        assert req.empty_timeout == 300
        assert req.departure_timeout == 60
        assert "sess-uuid-1234" in req.metadata

    @pytest.mark.asyncio
    async def test_create_call_room_idempotent_prefix(self, telephony_client, mock_livekit_api):
        """Room creation does not duplicate call_ prefix if already present."""
        expected_room = Room(name="call_already_prefixed")
        mock_livekit_api.room.create_room.return_value = expected_room

        room = await telephony_client.create_call_room("call_already_prefixed")

        assert room.name == "call_already_prefixed"
        req = mock_livekit_api.room.create_room.call_args[0][0]
        assert req.name == "call_already_prefixed"

    @pytest.mark.asyncio
    async def test_create_call_room_twirp_error_raises_room_creation_error(
        self, telephony_client, mock_livekit_api
    ):
        """Twirp errors are wrapped in RoomCreationError with descriptive message."""
        mock_livekit_api.room.create_room.side_effect = TwirpError(
            code=TwirpErrorCode.INTERNAL,
            msg="Internal database error",
            status=500,
        )

        with pytest.raises(RoomCreationError) as exc_info:
            await telephony_client.create_call_room("sess-error-500")

        assert "Internal database error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_call_room_empty_session_id_raises_value_error(self, telephony_client):
        """Empty session_id string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await telephony_client.create_call_room("   ")
        assert "session_id must not be empty" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Participant Token Generation Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTokenGeneration:
    """Tests for participant token generation with WebRTC audio grants."""

    def test_generate_participant_token_success(self, telephony_client):
        """Generates valid signed JWT token containing room and identity claims."""
        token_jwt = telephony_client.generate_participant_token(
            room_name="call_test_room",
            identity="voice_agent_worker_1",
            name="AI SDR Worker",
            ttl=1800,
            is_agent=True,
        )

        assert isinstance(token_jwt, str)
        assert len(token_jwt) > 20

        # Decode and verify JWT claims using secret
        decoded = jwt.decode(token_jwt, TEST_API_SECRET, algorithms=["HS256"])
        assert decoded["iss"] == TEST_API_KEY
        assert decoded["sub"] == "voice_agent_worker_1"
        assert decoded["name"] == "AI SDR Worker"
        assert decoded["video"]["room"] == "call_test_room"
        assert decoded["video"]["roomJoin"] is True
        assert decoded["video"]["agent"] is True

    def test_generate_participant_token_timedelta_ttl(self, telephony_client):
        """Accepts datetime.timedelta for TTL."""
        token_jwt = telephony_client.generate_participant_token(
            room_name="call_test_room",
            identity="worker_user",
            ttl=datetime.timedelta(minutes=15),
        )
        decoded = jwt.decode(token_jwt, TEST_API_SECRET, algorithms=["HS256"])
        assert decoded["sub"] == "worker_user"

    def test_generate_participant_token_missing_credentials_raises_error(self):
        """Raises TokenGenerationError if credentials are empty."""
        client = LiveKitTelephonyClient(url=TEST_URL, api_key="", api_secret="")
        with pytest.raises(TokenGenerationError) as exc_info:
            client.generate_participant_token(
                room_name="call_room",
                identity="agent",
            )
        assert "API key and secret required" in str(exc_info.value)

    def test_generate_participant_token_empty_identity_raises_error(self, telephony_client):
        """Raises TokenGenerationError if identity is empty."""
        with pytest.raises(TokenGenerationError) as exc_info:
            telephony_client.generate_participant_token(
                room_name="call_room",
                identity="",
            )
        assert "must not be empty" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Outbound SIP Dispatch Tests (Failover & Error Mapping)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSIPOutboundDispatch:
    """Tests for outbound SIP dispatching, carrier failover, and status codes."""

    @pytest.mark.asyncio
    async def test_dispatch_sip_outbound_success(self, telephony_client, mock_livekit_api):
        """Primary trunk dispatch succeeds and returns participant info."""
        expected_info = SIPParticipantInfo(
            participant_id="part_sip_123",
            participant_identity="sip_0912345678",
            room_name="call_lead_1",
            sip_call_id="call_viettel_001",
        )
        mock_livekit_api.sip.create_sip_participant.return_value = expected_info

        result = await telephony_client.dispatch_sip_outbound(
            phone_number="0912345678",
            trunk_id="trunk_viettel",
            room_name="lead_1",
            ringing_timeout=25,
            max_call_duration=175,
        )

        assert result.participant_id == "part_sip_123"
        assert result.sip_call_id == "call_viettel_001"

        req = mock_livekit_api.sip.create_sip_participant.call_args[0][0]
        assert req.sip_trunk_id == "trunk_viettel"
        assert req.sip_call_to == "0912345678"
        assert req.room_name == "call_lead_1"
        assert req.ringing_timeout.seconds == 25
        assert req.max_call_duration.seconds == 175

    @pytest.mark.asyncio
    async def test_dispatch_sip_outbound_failover_on_503_service_unavailable(
        self, telephony_client, mock_livekit_api
    ):
        """Primary trunk returning 503 triggers automatic failover to secondary trunk."""
        success_info = SIPParticipantInfo(
            participant_id="part_backup",
            sip_call_id="call_fpt_002",
        )

        # First call fails with 503 Unavailable, second call succeeds
        mock_livekit_api.sip.create_sip_participant.side_effect = [
            TwirpError(code=TwirpErrorCode.UNAVAILABLE, msg="503 Service Unavailable", status=503),
            success_info,
        ]

        result = await telephony_client.dispatch_sip_outbound(
            phone_number="+84987654321",
            trunk_id="trunk_viettel",
            fallback_trunk_ids=["trunk_fpt", "trunk_vnpt"],
            room_name="call_session_99",
        )

        assert result.participant_id == "part_backup"
        assert mock_livekit_api.sip.create_sip_participant.call_count == 2
        # Verify trunk IDs tried in order
        calls = mock_livekit_api.sip.create_sip_participant.call_args_list
        assert calls[0][0][0].sip_trunk_id == "trunk_viettel"
        assert calls[1][0][0].sip_trunk_id == "trunk_fpt"

    @pytest.mark.asyncio
    async def test_dispatch_sip_outbound_failover_on_486_busy(
        self, telephony_client, mock_livekit_api
    ):
        """Primary trunk returning 486 Busy triggers failover to fallback trunk."""
        success_info = SIPParticipantInfo(
            participant_id="part_secondary",
            sip_call_id="call_vnpt_003",
        )

        mock_livekit_api.sip.create_sip_participant.side_effect = [
            TwirpError(code=TwirpErrorCode.RESOURCE_EXHAUSTED, msg="486 Busy Here", status=486),
            success_info,
        ]

        result = await telephony_client.dispatch_sip_outbound(
            phone_number="0901122334",
            trunk_id="trunk_fpt",
            fallback_trunk_ids=["trunk_vnpt"],
            room_name="lead_100",
        )

        assert result.participant_id == "part_secondary"
        assert mock_livekit_api.sip.create_sip_participant.call_count == 2

    @pytest.mark.asyncio
    async def test_dispatch_sip_outbound_all_busy_raises_sip_trunk_busy_error(
        self, telephony_client, mock_livekit_api
    ):
        """When all candidate trunks return 486, raises SIPTrunkBusyError."""
        mock_livekit_api.sip.create_sip_participant.side_effect = [
            TwirpError(code=TwirpErrorCode.RESOURCE_EXHAUSTED, msg="486 Busy Here", status=486),
            TwirpError(code=TwirpErrorCode.RESOURCE_EXHAUSTED, msg="486 Busy Here", status=486),
        ]

        with pytest.raises(SIPTrunkBusyError) as exc_info:
            await telephony_client.dispatch_sip_outbound(
                phone_number="0909999888",
                trunk_id="trunk_viettel",
                fallback_trunk_ids=["trunk_fpt"],
                room_name="lead_busy",
            )

        err = exc_info.value
        assert err.sip_code == 486
        assert err.phone_number == "0909999888"
        assert err.attempted_trunks == ["trunk_viettel", "trunk_fpt"]

    @pytest.mark.asyncio
    async def test_dispatch_sip_outbound_all_unavailable_raises_service_unavailable_error(
        self, telephony_client, mock_livekit_api
    ):
        """When all candidate trunks return 503, raises SIPServiceUnavailableError."""
        mock_livekit_api.sip.create_sip_participant.side_effect = [
            TwirpError(code=TwirpErrorCode.UNAVAILABLE, msg="503 Service Unavailable", status=503),
            TwirpError(code=TwirpErrorCode.UNAVAILABLE, msg="503 Service Unavailable", status=503),
        ]

        with pytest.raises(SIPServiceUnavailableError) as exc_info:
            await telephony_client.dispatch_sip_outbound(
                phone_number="0909999888",
                trunk_id="trunk_viettel",
                fallback_trunk_ids=["trunk_cmc"],
                room_name="lead_down",
            )

        err = exc_info.value
        assert err.sip_code == 503
        assert err.attempted_trunks == ["trunk_viettel", "trunk_cmc"]

    @pytest.mark.asyncio
    async def test_dispatch_sip_outbound_codec_mismatch_raises_codec_not_acceptable(
        self, telephony_client, mock_livekit_api
    ):
        """Peer rejecting unsupported codec (488) raises SIPCodecNotAcceptableError."""
        mock_livekit_api.sip.create_sip_participant.side_effect = TwirpError(
            code=TwirpErrorCode.FAILED_PRECONDITION,
            msg="488 Not Acceptable Here: unsupported audio codec G.729",
            status=488,
        )

        with pytest.raises(SIPCodecNotAcceptableError) as exc_info:
            await telephony_client.dispatch_sip_outbound(
                phone_number="0911223344",
                trunk_id="trunk_fpt",
                room_name="lead_codec",
            )

        err = exc_info.value
        assert err.sip_code == 488

    @pytest.mark.asyncio
    async def test_dispatch_sip_outbound_not_found_raises_call_not_found_error(
        self, telephony_client, mock_livekit_api
    ):
        """Non-existent destination or trunk (404) raises SIPCallNotFoundError."""
        mock_livekit_api.sip.create_sip_participant.side_effect = TwirpError(
            code=TwirpErrorCode.NOT_FOUND,
            msg="404 Not Found: destination number unknown",
            status=404,
        )

        with pytest.raises(SIPCallNotFoundError) as exc_info:
            await telephony_client.dispatch_sip_outbound(
                phone_number="0999999999",
                trunk_id="trunk_viettel",
                room_name="lead_404",
            )

        err = exc_info.value
        assert err.sip_code == 404

    @pytest.mark.asyncio
    async def test_dispatch_sip_outbound_network_error_failover(
        self, telephony_client, mock_livekit_api
    ):
        """Network error on primary trunk fails over to fallback trunk."""
        success_info = SIPParticipantInfo(
            participant_id="part_net_backup",
            sip_call_id="call_net_001",
        )

        mock_livekit_api.sip.create_sip_participant.side_effect = [
            aiohttp.ClientConnectionError("Connection refused on primary SBC"),
            success_info,
        ]

        result = await telephony_client.dispatch_sip_outbound(
            phone_number="0901234567",
            trunk_id="trunk_primary",
            fallback_trunk_ids=["trunk_secondary"],
            room_name="lead_net_failover",
        )

        assert result.participant_id == "part_net_backup"
        assert mock_livekit_api.sip.create_sip_participant.call_count == 2


# ---------------------------------------------------------------------------
# Client Lifecycle & Resource Management Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestClientLifecycle:
    """Tests for async context management and connection closing."""

    @pytest.mark.asyncio
    async def test_async_context_manager_clean_exit(self):
        """Async context manager exits cleanly and closes owned LiveKitAPI."""
        client = LiveKitTelephonyClient(
            url=TEST_URL,
            api_key=TEST_API_KEY,
            api_secret=TEST_API_SECRET,
        )

        with patch("app.services.voice.telephony_client.LiveKitAPI") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.aclose = AsyncMock()
            mock_cls.return_value = mock_inst

            async with client as ctx:
                assert ctx is client
                await ctx._get_api()  # Trigger initialization

            mock_inst.aclose.assert_awaited_once()
            assert client._api is None

    @pytest.mark.asyncio
    async def test_owned_api_closed_on_aclose(self):
        """Client closes internally owned LiveKitAPI on aclose."""
        client = LiveKitTelephonyClient(
            url=TEST_URL,
            api_key=TEST_API_KEY,
            api_secret=TEST_API_SECRET,
        )

        with patch("app.services.voice.telephony_client.LiveKitAPI") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.aclose = AsyncMock()
            mock_cls.return_value = mock_inst

            # Trigger lazy creation
            api = await client._get_api()
            assert api is mock_inst

            await client.aclose()
            mock_inst.aclose.assert_awaited_once()
            assert client._api is None

    @pytest.mark.asyncio
    async def test_missing_credentials_raises_telephony_error(self):
        """Lazy _get_api raises TelephonyError if credentials missing."""
        client = LiveKitTelephonyClient(url="", api_key="", api_secret="")
        with pytest.raises(TelephonyError) as exc_info:
            await client._get_api()
        assert "must be configured" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Edge Case Tests (added in Step-04 Review Pass)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestReviewPatchedEdgeCases:
    """Tests for edge cases identified during Step-04 code review."""

    @pytest.mark.asyncio
    async def test_dispatch_sip_outbound_empty_trunk_raises_dispatch_error(
        self, telephony_client
    ):
        """Empty or whitespace trunk_id raises SIPDispatchError immediately."""
        with pytest.raises(SIPDispatchError) as exc_info:
            await telephony_client.dispatch_sip_outbound(
                phone_number="0912345678",
                trunk_id="   ",
                room_name="call_room",
            )
        assert "trunk_id must not be empty" in str(exc_info.value)

    def test_normalize_phone_number_non_string_raises_value_error(self):
        """Non-string phone_number raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            LiveKitTelephonyClient.normalize_phone_number(123456789)  # type: ignore
        assert "phone_number must be a string" in str(exc_info.value)

    def test_normalize_phone_number_invalid_format_raises_value_error(self):
        """Malformed phone number (e.g. contains letters) raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            LiveKitTelephonyClient.normalize_phone_number("09123abc78")
        assert "not a valid E.164" in str(exc_info.value)

    def test_generate_participant_token_negative_ttl_raises_error(self, telephony_client):
        """Zero or negative ttl raises TokenGenerationError."""
        with pytest.raises(TokenGenerationError) as exc_info:
            telephony_client.generate_participant_token(
                room_name="call_room",
                identity="agent_1",
                ttl=0,
            )
        assert "ttl must be a positive" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_session_id_with_special_characters_escaped_in_metadata(
        self, telephony_client, mock_livekit_api
    ):
        """Session ID containing quotes/slashes produces valid JSON metadata."""
        mock_livekit_api.room.create_room.return_value = Room(name="call_room_clean")
        await telephony_client.create_call_room('sess"quote\\slash')
        req = mock_livekit_api.room.create_room.call_args[0][0]
        # Must parse cleanly as JSON
        import json
        parsed = json.loads(req.metadata)
        assert parsed["session_id"] == 'sess"quote\\slash'
