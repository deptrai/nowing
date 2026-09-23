"""Smart Meeting Booking Engine for Auto-Reply (Story 37.3 / AD-117).

Extracts calendar free/busy across Google Calendar & Lark Calendar using
workspace credentials, proposes concrete ICT slots via the two-way auto-reply
agent, soft-locks proposed slots in Redis (15-minute TTL,
``lock:calendar_slot:{user_id}:{slot}``), and books the confirmed meeting with
a Google Meet / Lark Video link, syncing the CRM lead to ``meeting_scheduled``.

Timezone rule (AD-117): all stored/locked values are ISO-8601 UTC; ICT
(UTC+7) formatting happens only when rendering proposal text.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import SearchSourceConnector, SearchSourceConnectorType
from app.services.sequencer.constants import VN_TZ

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (AC-1 / AC-2 / AC-5)
# ---------------------------------------------------------------------------

# Working hours in ICT minutes-of-day: 09:00-12:00 and 13:30-17:30, Mon-Fri.
WORKING_WINDOWS: tuple[tuple[int, int], ...] = (
    (9 * 60, 12 * 60),
    (13 * 60 + 30, 17 * 60 + 30),
)
BUSINESS_DAYS = 5
SLOT_BUFFER_MINUTES = 15
DEFAULT_SLOT_MINUTES = 30
SLOT_LOCK_TTL_SECONDS = 15 * 60
SLOT_LOCK_KEY_TEMPLATE = "lock:calendar_slot:{user_id}:{slot_timestamp}"
STATE_KEY_TEMPLATE = "meeting_booking:state:{workspace_id}:{thread_id}"
STATE_TTL_SECONDS = 24 * 3600
MAX_NEGOTIATION_TURNS = 2
PROPOSAL_COUNT = 3
# ponytail: give the prospect a small heads-up so we never propose a slot that
# starts while the reply is still in flight.
MIN_NOTICE_MINUTES = 30

MEETING_SCHEDULED_STATUS = "meeting_scheduled"
HUMAN_TAKEOVER_TAG = "human_takeover_needed"

VI_WEEKDAYS = [
    "Thứ Hai",
    "Thứ Ba",
    "Thứ Tư",
    "Thứ Năm",
    "Thứ Sáu",
    "Thứ Bảy",
    "Chủ Nhật",
]

LARK_API_BASE = "https://open.larksuite.com/open-apis"

# ---------------------------------------------------------------------------
# Intent / confirmation / rejection parsing (deterministic, $0 token)
# ---------------------------------------------------------------------------

MEETING_INTENT_PHRASES: tuple[str, ...] = (
    "hẹn gặp",
    "đặt lịch",
    "lên lịch",
    "lịch hẹn",
    "hẹn lịch",
    "hẹn xem",
    "lịch xem",
    "sắp xếp họp",
    "sắp xếp cuộc họp",
    "sắp xếp lịch",
    "cuộc họp",
    "họp trực tuyến",
    "họp online",
    "gọi video",
    "gặp mặt",
    "gặp trực tiếp",
    "trao đổi trực tiếp",
    "tư vấn trực tiếp",
    "xem demo",
    "demo trực tiếp",
    "xếp lịch",
    "đặt hẹn",
    "hẹn",
    "schedule a meeting",
    "book a meeting",
    "book a call",
    "set up a call",
    "meeting",
)

REJECTION_PHRASES: tuple[str, ...] = (
    "không rảnh",
    "ko rảnh",
    "bận",
    "không được",
    "ko được",
    "không tiện",
    "đổi lịch",
    "đổi giờ",
    "đổi sang",
    "hôm khác",
    "lịch khác",
    "giờ khác",
    "ngày khác",
    "khung khác",
    "dời lịch",
    "dời sang",
    "hoãn",
    "không hợp",
    "không phù hợp",
    "không đi được",
    "khác đi",
    "chưa được",
)

_GENERIC_CONFIRM_RE = re.compile(
    r"^\s*(dạ\s+)?(ok|okay|oke|okie|được|đồng ý|chốt|vâng|vang|yes|yeah|"
    r"confirm|xác nhận|đặt luôn|chốt lịch|chuẩn)([\s!.ạ]*)$",
    re.IGNORECASE,
)

_ORDINAL_RE = re.compile(
    r"(?:option|lựa chọn|phương án|phuong an|số|so|slot|khung|cái|ca|"
    r"lịch|lich)\s*(?:thứ\s*|thu\s*)?(\d)\b",
    re.IGNORECASE,
)
_ORDINAL_WORDS = {
    "đầu tiên": 1,
    "dau tien": 1,
    "thứ nhất": 1,
    "thu nhat": 1,
    "đầu": 1,
}
_HHMM_RE = re.compile(r"\b(\d{1,2})[:h](\d{2})\b")
_HH_RE = re.compile(r"\b(\d{1,2})\s*(?:h|giờ|gio)\b")
_BARE_DIGIT_RE = re.compile(r"(?<![\d:])([1-9])(?![\d:h])")
# Vietnamese part-of-day markers that shift a bare hour into the afternoon.
_PM_MARKERS = ("chiều", "chieu", "tối", "toi", "đêm", "dem")
_NOON_MARKERS = ("trưa", "trua")
# Negation immediately before a phrase (e.g. "không bận", "chưa cần hẹn")
# inverts its meaning - detect intent/rejection must skip such matches.
_NEGATION_RE = re.compile(
    r"(?:không|ko|chưa|chua|đừng|dung|khỏi|đâu|dau)"
    r"(?:\s+[\wàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]*){0,2}\s*$"
)


def _phrase_present(text: str, phrase: str) -> bool:
    """True when ``phrase`` occurs in ``text`` not preceded by a negation."""
    start = 0
    while True:
        idx = text.find(phrase, start)
        if idx == -1:
            return False
        prefix = text[max(0, idx - 30) : idx]
        if not _NEGATION_RE.search(prefix):
            return True
        start = idx + 1

_VI_WEEKDAY_ALIASES = {
    "thứ hai": 0,
    "thu hai": 0,
    "thứ 2": 0,
    "thu 2": 0,
    "thứ ba": 1,
    "thu ba": 1,
    "thứ 3": 1,
    "thu 3": 1,
    "thứ tư": 2,
    "thu tu": 2,
    "thứ 4": 2,
    "thu 4": 2,
    "thứ năm": 3,
    "thu nam": 3,
    "thứ 5": 3,
    "thu 5": 3,
    "thứ sáu": 4,
    "thu sau": 4,
    "thứ 6": 4,
    "thu 6": 4,
    "thứ bảy": 5,
    "thu bay": 5,
    "thứ 7": 5,
    "thu 7": 5,
    "chủ nhật": 6,
    "chu nhat": 6,
}


def detect_meeting_intent(text: str | None) -> bool:
    """True when the prospect message asks to schedule / meet (AC-1 trigger)."""
    if not text:
        return False
    normalized = text.lower()
    return any(
        _phrase_present(normalized, phrase) for phrase in MEETING_INTENT_PHRASES
    )


def detect_slot_rejection(text: str | None) -> bool:
    """True when the prospect rejects the proposed slots (AC-5 turn counter)."""
    if not text:
        return False
    normalized = text.lower()
    return any(
        _phrase_present(normalized, phrase) for phrase in REJECTION_PHRASES
    )


def detect_generic_confirmation(text: str | None) -> bool:
    """True for bare affirmatives (ok / được / chốt / đồng ý / xác nhận)."""
    if not text:
        return False
    return bool(_GENERIC_CONFIRM_RE.match(text.strip()))


def parse_slot_choice(text: str, slots: list[CalendarSlot]) -> int | None:
    """Resolve which proposed slot the prospect picked; ``None`` if unclear.

    Matches explicit time mentions ("14:00", "14h", "2 giờ chiều"),
    ordinal picks ("option 2", "số 1", "cái đầu tiên", bare "2"), and
    weekday names ("thứ ba") when they identify exactly one proposal.
    """
    if not text or not slots:
        return None
    normalized = text.lower()

    # 1) Explicit time reference, shifted by part-of-day markers
    #    ("2 giờ chiều" = 14:00, "1 giờ trưa" = 13:00).
    pm_shift = any(marker in normalized for marker in _PM_MARKERS)
    noon_shift = any(marker in normalized for marker in _NOON_MARKERS)

    def _hour_to_minutes(hour: int) -> int | None:
        if not 0 <= hour <= 23:
            return None
        if (pm_shift and hour < 12) or (noon_shift and hour < 11):
            hour += 12
        return hour * 60

    mentioned_minutes: list[int] = []
    for hh, mm in _HHMM_RE.findall(normalized):
        base = _hour_to_minutes(int(hh))
        if base is not None:
            mentioned_minutes.append(base + int(mm))
    for hh in _HH_RE.findall(normalized):
        base = _hour_to_minutes(int(hh))
        if base is not None:
            mentioned_minutes.append(base)
    if mentioned_minutes:
        for idx, slot in enumerate(slots):
            local = slot.start.astimezone(VN_TZ)
            if local.hour * 60 + local.minute in mentioned_minutes:
                return idx
        return None  # a time was mentioned but matches no proposal

    # Weekday mentions ("thứ hai", "thứ 2") take precedence over bare
    # ordinals, so strip them before looking for "option 2" / "2".
    stripped = normalized
    for alias in _VI_WEEKDAY_ALIASES:
        stripped = stripped.replace(alias, " ")

    # 2) Ordinal reference ("option 2", "số 1", "lịch 2", ...).
    match = _ORDINAL_RE.search(stripped)
    if match:
        ordinal = int(match.group(1))
        if 1 <= ordinal <= len(slots):
            return ordinal - 1
        return None

    # 3) Bare digit pick ("2", "chọn 3").
    match = _BARE_DIGIT_RE.search(stripped)
    if match:
        ordinal = int(match.group(1))
        if 1 <= ordinal <= len(slots):
            return ordinal - 1
        return None

    # 4) Weekday-only reference that resolves to exactly one proposal.
    matched_weekdays = {
        day for alias, day in _VI_WEEKDAY_ALIASES.items() if alias in normalized
    }
    if len(matched_weekdays) == 1:
        day = next(iter(matched_weekdays))
        candidates = [
            idx
            for idx, slot in enumerate(slots)
            if slot.start.astimezone(VN_TZ).weekday() == day
        ]
        if len(candidates) == 1:
            return candidates[0]

    # 5) Ordinal words ("cái đầu tiên", "thứ nhất") with a picker keyword.
    for phrase, ordinal in _ORDINAL_WORDS.items():
        if phrase in stripped:
            if any(
                kw in stripped
                for kw in ("cái", "ca", "option", "lựa chọn", "phương án", "số")
            ) and ordinal <= len(slots):
                return ordinal - 1
            break

    return None


# ---------------------------------------------------------------------------
# Slot model & formatting
# ---------------------------------------------------------------------------


@dataclass
class CalendarSlot:
    """A proposed meeting slot. ``start``/``end`` are tz-aware datetimes."""

    start: datetime
    end: datetime

    def start_ict(self) -> datetime:
        return self.start.astimezone(VN_TZ)

    def label_ict(self) -> str:
        """AC-3: "14:00 Thứ Ba" - localized ICT rendering for templates."""
        local = self.start_ict()
        return f"{local:%H:%M} {VI_WEEKDAYS[local.weekday()]}"

    def lock_timestamp(self) -> int:
        """Epoch seconds of the slot start - the ``{slot}`` in the lock key."""
        return int(self.start.astimezone(UTC).timestamp())

    def to_dict(self) -> dict[str, str]:
        return {
            "start": self.start.astimezone(UTC).isoformat(),
            "end": self.end.astimezone(UTC).isoformat(),
            "label": self.label_ict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> CalendarSlot:
        start = datetime.fromisoformat(data["start"])
        end = datetime.fromisoformat(data["end"])
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        return cls(start=start, end=end)


def format_slot_ict(start: datetime) -> str:
    """AC-3 helper: render an aware datetime as "14:00 Thứ Ba" in ICT."""
    return CalendarSlot(start=start, end=start).label_ict()


def iter_business_days(now: datetime, days: int = BUSINESS_DAYS):
    """Yield the next ``days`` Mon-Fri dates (ICT), starting from today."""
    current = now.astimezone(VN_TZ).date()
    yielded = 0
    while yielded < days:
        if current.weekday() < 5:  # Monday-Friday only
            yield current
            yielded += 1
        current += timedelta(days=1)


def compute_free_slots(
    busy_intervals: list[tuple[datetime, datetime]],
    now: datetime | None = None,
    *,
    days: int = BUSINESS_DAYS,
    slot_minutes: int = DEFAULT_SLOT_MINUTES,
    buffer_minutes: int = SLOT_BUFFER_MINUTES,
    min_notice_minutes: int = MIN_NOTICE_MINUTES,
) -> list[CalendarSlot]:
    """Compute free candidate slots inside ICT working hours.

    Slots are aligned to ``slot_minutes`` boundaries within each working
    window, must not overlap any busy interval expanded by a 15-minute buffer
    on both sides, and must start at least ``min_notice_minutes`` in the future.
    """
    if now is None:
        now = datetime.now(VN_TZ)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    now_ict = now.astimezone(VN_TZ)
    earliest_start = now_ict + timedelta(minutes=min_notice_minutes)

    buffer = timedelta(minutes=buffer_minutes)
    normalized_busy: list[tuple[datetime, datetime]] = []
    for b_start, b_end in busy_intervals:
        if b_start.tzinfo is None:
            b_start = b_start.replace(tzinfo=UTC)
        if b_end.tzinfo is None:
            b_end = b_end.replace(tzinfo=UTC)
        normalized_busy.append((b_start - buffer, b_end + buffer))

    duration = timedelta(minutes=slot_minutes)
    step = timedelta(minutes=slot_minutes)
    free: list[CalendarSlot] = []

    for day in iter_business_days(now_ict, days=days):
        for win_start_min, win_end_min in WORKING_WINDOWS:
            window_start = datetime.combine(
                day, time(win_start_min // 60, win_start_min % 60), tzinfo=VN_TZ
            )
            window_end = datetime.combine(
                day, time(win_end_min // 60, win_end_min % 60), tzinfo=VN_TZ
            )
            cursor = window_start
            while cursor + duration <= window_end:
                slot_end = cursor + duration
                if cursor >= earliest_start and not any(
                    cursor < b_end and slot_end > b_start
                    for b_start, b_end in normalized_busy
                ):
                    free.append(CalendarSlot(start=cursor, end=slot_end))
                cursor += step
    return free


def select_proposals(
    free_slots: list[CalendarSlot], count: int = PROPOSAL_COUNT
) -> list[CalendarSlot]:
    """Pick up to ``count`` proposals, round-robin across days for spread."""
    by_day: dict[Any, list[CalendarSlot]] = {}
    for slot in free_slots:
        by_day.setdefault(slot.start_ict().date(), []).append(slot)

    picked: list[CalendarSlot] = []
    days = sorted(by_day)
    round_idx = 0
    while len(picked) < count and days:
        progressed = False
        for day in days:
            day_slots = by_day[day]
            if round_idx < len(day_slots):
                picked.append(day_slots[round_idx])
                progressed = True
                if len(picked) >= count:
                    break
        if not progressed:
            break
        round_idx += 1
    return picked


# ---------------------------------------------------------------------------
# Calendar provider clients
# ---------------------------------------------------------------------------


@dataclass
class CalendarCredentials:
    """Resolved workspace calendar credentials."""

    provider: str  # "google_native" | "google_composio" | "lark"
    connector_id: int
    user_id: str
    config: dict[str, Any]


class LarkCalendarClient:
    """Lark Calendar API client (freebusy + event create with Lark Video)."""

    def __init__(
        self,
        *,
        app_id: str | None = None,
        app_secret: str | None = None,
        tenant_access_token: str | None = None,
        user_access_token: str | None = None,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.tenant_access_token = tenant_access_token
        self.user_access_token = user_access_token

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        if self.user_access_token:
            return self.user_access_token
        if self.tenant_access_token:
            return self.tenant_access_token
        if self.app_id and self.app_secret:
            res = await client.post(
                f"{LARK_API_BASE}/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            data = res.json()
            token = data.get("tenant_access_token")
            if not token:
                raise RuntimeError(
                    f"Lark tenant_access_token fetch failed: {data.get('msg')}"
                )
            self.tenant_access_token = token
            return token
        raise RuntimeError("No Lark calendar credentials configured")

    async def list_busy_intervals(
        self,
        user_id: str,
        time_min: datetime,
        time_max: datetime,
        *,
        calendar_id: str | None = None,
        user_id_type: str = "open_id",
    ) -> list[tuple[datetime, datetime]]:
        """Query ``calendar/v4/freebusy/list`` for a Lark user's busy blocks.

        ``user_id`` is a top-level body field (its type is selected via the
        ``user_id_type`` query param); ``items`` carries ``{calendar_id}``
        entries naming the calendars to check.
        """
        body = {
            "time_min": time_min.astimezone(UTC).isoformat(),
            "time_max": time_max.astimezone(UTC).isoformat(),
            "user_id": user_id,
            "items": [{"calendar_id": calendar_id}] if calendar_id else [],
            "only_busy": True,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await self._access_token(client)
            res = await client.post(
                f"{LARK_API_BASE}/calendar/v4/freebusy/list",
                params={"user_id_type": user_id_type},
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = res.json()
        if data.get("code") != 0:
            raise RuntimeError(
                f"Lark freebusy error {data.get('code')}: {data.get('msg')}"
            )

        busy: list[tuple[datetime, datetime]] = []
        inner = data.get("data") or {}
        # Lark returns freebusy_list items each carrying busy slots; the exact
        # envelope has shifted across API versions, so walk tolerantly.
        for block in self._walk_busy_slots(inner):
            start = self._parse_lark_dt(block.get("start_time") or block.get("start"))
            end = self._parse_lark_dt(block.get("end_time") or block.get("end"))
            if start and end:
                busy.append((start, end))
        return busy

    @classmethod
    def _walk_busy_slots(cls, node: Any) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, list) and (
                    "busy" in key or key in ("freebusy_list", "busy_slots")
                ):
                    for item in value:
                        if isinstance(item, dict):
                            if item.get("start_time") or item.get("start"):
                                found.append(item)
                            else:
                                found.extend(cls._walk_busy_slots(item))
                elif isinstance(value, (dict, list)):
                    found.extend(cls._walk_busy_slots(value))
        elif isinstance(node, list):
            for item in node:
                found.extend(cls._walk_busy_slots(item))
        return found

    @staticmethod
    def _parse_lark_dt(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            # Lark emits unix timestamps (seconds or milliseconds).
            ts = float(value)
            if ts > 1e12:
                ts /= 1000.0
            return datetime.fromtimestamp(ts, tz=UTC)
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                try:
                    return LarkCalendarClient._parse_lark_dt(float(value))
                except ValueError:
                    return None
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        return None

    async def create_event(
        self,
        *,
        calendar_id: str,
        summary: str,
        start: datetime,
        end: datetime,
        attendee_email: str | None = None,
        description: str | None = None,
    ) -> tuple[str | None, str | None]:
        """Create a Lark Calendar event with a Lark Video (vc) room.

        Returns ``(event_id, meeting_url_or_html_link)``.
        """
        payload: dict[str, Any] = {
            "summary": summary,
            "start_time": {
                "timestamp": str(int(start.astimezone(UTC).timestamp())),
                "timezone": "Asia/Ho_Chi_Minh",
            },
            "end_time": {
                "timestamp": str(int(end.astimezone(UTC).timestamp())),
                "timezone": "Asia/Ho_Chi_Minh",
            },
            "vchat": {"vc_type": "vc"},
            "need_notification": True,
        }
        if description:
            payload["description"] = description
        if attendee_email:
            payload["attendees"] = [
                {
                    "type": "third_party",
                    "third_party_email": attendee_email,
                    "is_optional": False,
                }
            ]

        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await self._access_token(client)
            res = await client.post(
                f"{LARK_API_BASE}/calendar/v4/calendars/{calendar_id}/events",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = res.json()
        if data.get("code") != 0:
            raise RuntimeError(
                f"Lark create event error {data.get('code')}: {data.get('msg')}"
            )
        event = (data.get("data") or {}).get("event") or {}
        meeting_link = (
            (event.get("vchat") or {}).get("meeting_url")
            or event.get("app_link")
            or event.get("html_link")
        )
        return event.get("event_id"), meeting_link


# ---------------------------------------------------------------------------
# Availability service (AC-1)
# ---------------------------------------------------------------------------


class CalendarAvailabilityService:
    """Free/busy extraction across the workspace's connected calendars."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve_credentials(
        self, workspace_id: int
    ) -> list[CalendarCredentials]:
        """All connected calendar connectors for the workspace, primary first."""
        stmt = (
            select(SearchSourceConnector)
            .where(
                SearchSourceConnector.workspace_id == workspace_id,
                SearchSourceConnector.connector_type.in_(
                    [
                        SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
                        SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
                        SearchSourceConnectorType.LARK_CALENDAR_CONNECTOR,
                    ]
                ),
            )
            .order_by(SearchSourceConnector.created_at.desc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()

        creds: list[CalendarCredentials] = []
        for connector in rows:
            provider = self._provider_for(connector.connector_type)
            if provider is None:
                continue
            creds.append(
                CalendarCredentials(
                    provider=provider,
                    connector_id=connector.id,
                    user_id=str(connector.user_id),
                    config=dict(connector.config or {}),
                )
            )
        return creds

    @staticmethod
    def _provider_for(
        connector_type: SearchSourceConnectorType,
    ) -> str | None:
        if connector_type == SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR:
            return "google_native"
        if (
            connector_type
            == SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR
        ):
            return "google_composio"
        if connector_type == SearchSourceConnectorType.LARK_CALENDAR_CONNECTOR:
            return "lark"
        return None

    def _decrypt_native_google_config(
        self, config_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Decrypt native Google OAuth config (same envelope as the indexer)."""
        if not config_data.get("_token_encrypted") or not config.SECRET_KEY:
            return dict(config_data)
        from app.utils.oauth_security import TokenEncryption

        token_encryption = TokenEncryption(config.SECRET_KEY)
        decrypted = dict(config_data)
        for key in ("token", "refresh_token", "client_secret"):
            if decrypted.get(key):
                decrypted[key] = token_encryption.decrypt_token(decrypted[key])
        return decrypted

    def _build_google_credentials(self, config_data: dict[str, Any]):
        from google.oauth2.credentials import Credentials

        decrypted = self._decrypt_native_google_config(config_data)
        exp = decrypted.get("expiry", "")
        if exp:
            exp = str(exp).replace("Z", "")
        return Credentials(
            token=decrypted.get("token"),
            refresh_token=decrypted.get("refresh_token"),
            token_uri=decrypted.get("token_uri"),
            client_id=decrypted.get("client_id"),
            client_secret=decrypted.get("client_secret"),
            scopes=decrypted.get("scopes", []),
            expiry=datetime.fromisoformat(exp) if exp else None,
        )

    @staticmethod
    def _parse_event_window(event: dict[str, Any]) -> tuple[datetime, datetime] | None:
        start_raw = (event.get("start") or {}).get("dateTime") or (
            event.get("start") or {}
        ).get("date")
        end_raw = (event.get("end") or {}).get("dateTime") or (
            event.get("end") or {}
        ).get("date")
        if not start_raw or not end_raw:
            return None
        try:
            start = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(end_raw).replace("Z", "+00:00"))
        except ValueError:
            return None
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        return start, end

    async def get_busy_intervals(
        self,
        credential: CalendarCredentials,
        time_min: datetime,
        time_max: datetime,
    ) -> list[tuple[datetime, datetime]]:
        """Fetch busy intervals from one credential (provider dispatch)."""
        try:
            if credential.provider == "google_native":
                return await self._google_native_busy(
                    credential, time_min, time_max
                )
            if credential.provider == "google_composio":
                return await self._google_composio_busy(
                    credential, time_min, time_max
                )
            if credential.provider == "lark":
                return await self._lark_busy(credential, time_min, time_max)
        except Exception:
            logger.warning(
                "Calendar free/busy fetch failed for provider=%s connector=%s",
                credential.provider,
                credential.connector_id,
                exc_info=True,
            )
        return []

    async def _google_native_busy(
        self,
        credential: CalendarCredentials,
        time_min: datetime,
        time_max: datetime,
    ) -> list[tuple[datetime, datetime]]:
        from app.connectors.google_calendar_connector import (
            GoogleCalendarConnector,
        )

        creds = self._build_google_credentials(credential.config)
        # The connector's googleapiclient .execute() is synchronous, so the
        # whole call runs in a worker thread. session=None keeps the
        # main-loop AsyncSession out of that thread (a refreshed token is
        # simply not persisted - refreshed again next call).
        client = GoogleCalendarConnector(
            credentials=creds,
            session=None,
            user_id=credential.user_id,
            connector_id=credential.connector_id,
        )

        def _fetch() -> tuple[list[dict[str, Any]], str | None]:
            return asyncio.run(
                client.get_all_primary_calendar_events(
                    start_date=time_min.date().isoformat(),
                    end_date=time_max.date().isoformat(),
                )
            )

        events, error = await asyncio.to_thread(_fetch)
        if error and not events:
            if "No events found" in error:
                return []
            logger.warning("Google native busy fetch error: %s", error)
            return []
        return [
            window
            for window in (self._parse_event_window(e) for e in events)
            if window is not None
        ]

    async def _google_composio_busy(
        self,
        credential: CalendarCredentials,
        time_min: datetime,
        time_max: datetime,
    ) -> list[tuple[datetime, datetime]]:
        from app.services.composio_service import ComposioService

        connected_account_id = credential.config.get(
            "composio_connected_account_id"
        )
        if not connected_account_id:
            return []
        service = ComposioService()
        events, error = await service.get_calendar_events(
            connected_account_id=connected_account_id,
            entity_id=f"nowing_{credential.user_id}",
            time_min=time_min.astimezone(UTC).isoformat(),
            time_max=time_max.astimezone(UTC).isoformat(),
            max_results=250,
        )
        if error and not events:
            logger.warning("Composio calendar busy fetch error: %s", error)
            return []
        return [
            window
            for window in (self._parse_event_window(e) for e in events)
            if window is not None
        ]

    async def _lark_busy(
        self,
        credential: CalendarCredentials,
        time_min: datetime,
        time_max: datetime,
    ) -> list[tuple[datetime, datetime]]:
        client = self._build_lark_client(credential.config)
        lark_user_id = (
            credential.config.get("lark_user_id")
            or credential.config.get("user_id")
            or credential.config.get("open_id")
        )
        if not lark_user_id:
            logger.warning(
                "Lark connector %s missing lark_user_id; cannot query freebusy",
                credential.connector_id,
            )
            return []
        return await client.list_busy_intervals(
            str(lark_user_id),
            time_min,
            time_max,
            calendar_id=credential.config.get("calendar_id"),
            user_id_type=credential.config.get("user_id_type") or "open_id",
        )

    @staticmethod
    def _build_lark_client(config_data: dict[str, Any]) -> LarkCalendarClient:
        cfg = dict(config_data)
        if cfg.get("_token_encrypted") and config.SECRET_KEY:
            from app.utils.oauth_security import TokenEncryption

            enc = TokenEncryption(config.SECRET_KEY)
            for key in (
                "app_secret",
                "tenant_access_token",
                "user_access_token",
            ):
                if cfg.get(key):
                    try:
                        cfg[key] = enc.decrypt_token(cfg[key])
                    except Exception:
                        logger.debug("Lark config decrypt failed for %s", key)
        return LarkCalendarClient(
            app_id=cfg.get("app_id"),
            app_secret=cfg.get("app_secret"),
            tenant_access_token=cfg.get("tenant_access_token"),
            user_access_token=cfg.get("user_access_token"),
        )

    async def compute_availability(
        self,
        workspace_id: int,
        *,
        days: int = BUSINESS_DAYS,
        slot_minutes: int = DEFAULT_SLOT_MINUTES,
        now: datetime | None = None,
    ) -> tuple[list[CalendarSlot], list[CalendarCredentials]]:
        """Free slots merged across all connected calendars + credentials."""
        credentials = await self.resolve_credentials(workspace_id)
        if not credentials:
            return [], []
        if now is None:
            now = datetime.now(VN_TZ)
        time_min = now
        time_max = now + timedelta(days=days + 3)  # slack for weekends
        busy: list[tuple[datetime, datetime]] = []
        for credential in credentials:
            busy.extend(
                await self.get_busy_intervals(credential, time_min, time_max)
            )
        return (
            compute_free_slots(busy, now=now, days=days, slot_minutes=slot_minutes),
            credentials,
        )

    # -- event creation ----------------------------------------------------

    async def create_event(
        self,
        credential: CalendarCredentials,
        *,
        summary: str,
        start: datetime,
        end: datetime,
        attendee_email: str | None = None,
        description: str | None = None,
    ) -> tuple[str | None, str | None]:
        """Create a calendar event with a video link; ``(event_id, link)``."""
        if credential.provider == "google_native":
            return await self._create_google_native_event(
                credential,
                summary=summary,
                start=start,
                end=end,
                attendee_email=attendee_email,
                description=description,
            )
        if credential.provider == "google_composio":
            return await self._create_composio_event(
                credential,
                summary=summary,
                start=start,
                end=end,
                attendee_email=attendee_email,
                description=description,
            )
        if credential.provider == "lark":
            client = self._build_lark_client(credential.config)
            # Lark has no "primary" alias - the concrete calendar id must be
            # stored on the connector config.
            calendar_id = credential.config.get("calendar_id")
            if not calendar_id:
                raise RuntimeError(
                    "Lark connector missing calendar_id "
                    f"(connector_id={credential.connector_id})"
                )
            return await client.create_event(
                calendar_id=calendar_id,
                summary=summary,
                start=start,
                end=end,
                attendee_email=attendee_email,
                description=description,
            )
        raise RuntimeError(f"Unknown calendar provider {credential.provider}")

    async def _create_google_native_event(
        self,
        credential: CalendarCredentials,
        *,
        summary: str,
        start: datetime,
        end: datetime,
        attendee_email: str | None,
        description: str | None,
    ) -> tuple[str | None, str | None]:
        from googleapiclient.discovery import build

        creds = self._build_google_credentials(credential.config)

        # Refresh synchronously via the connector helper when expired.
        if creds.expired or not creds.valid:
            from app.connectors.google_calendar_connector import (
                GoogleCalendarConnector,
            )

            connector = GoogleCalendarConnector(
                credentials=creds,
                session=self.session,
                user_id=credential.user_id,
                connector_id=credential.connector_id,
            )
            creds = await connector._get_credentials()

        body: dict[str, Any] = {
            "summary": summary,
            "start": {
                "dateTime": start.astimezone(VN_TZ).isoformat(),
                "timeZone": "Asia/Ho_Chi_Minh",
            },
            "end": {
                "dateTime": end.astimezone(VN_TZ).isoformat(),
                "timeZone": "Asia/Ho_Chi_Minh",
            },
            # Ask Google to attach a Meet room (AC-4).
            "conferenceData": {
                "createRequest": {
                    "requestId": uuid.uuid4().hex,
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }
        if description:
            body["description"] = description
        if attendee_email:
            body["attendees"] = [{"email": attendee_email}]

        def _insert() -> dict[str, Any]:
            service = build("calendar", "v3", credentials=creds)
            return (
                service.events()
                .insert(
                    calendarId="primary",
                    body=body,
                    conferenceDataVersion=1,
                    sendUpdates="all",  # sends the calendar invite to attendees
                )
                .execute()
            )

        event = await asyncio.to_thread(_insert)
        link = event.get("hangoutLink") or event.get("htmlLink")
        return event.get("id"), link

    async def _create_composio_event(
        self,
        credential: CalendarCredentials,
        *,
        summary: str,
        start: datetime,
        end: datetime,
        attendee_email: str | None,
        description: str | None,
    ) -> tuple[str | None, str | None]:
        from app.services.composio_service import ComposioService

        connected_account_id = credential.config.get(
            "composio_connected_account_id"
        )
        if not connected_account_id:
            raise RuntimeError("Composio connected_account_id not configured")
        service = ComposioService()
        attendees = [attendee_email] if attendee_email else None
        event_id, html_link, error = await service.create_calendar_event(
            connected_account_id=connected_account_id,
            entity_id=f"nowing_{credential.user_id}",
            summary=summary,
            start_datetime=start.astimezone(VN_TZ).isoformat(),
            end_datetime=end.astimezone(VN_TZ).isoformat(),
            timezone="Asia/Ho_Chi_Minh",
            description=description,
            attendees=attendees,
            create_meeting_room=True,
        )
        if error:
            raise RuntimeError(error)
        return event_id, html_link


# ---------------------------------------------------------------------------
# Booking orchestration (AC-2/3/4/5)
# ---------------------------------------------------------------------------


@dataclass
class MeetingTurnResult:
    """Outcome of one inbound text through the booking state machine."""

    reply_text: str
    booked: bool = False
    escalated: bool = False
    reason: str = ""
    slot: CalendarSlot | None = None
    event_id: str | None = None
    meeting_link: str | None = None


@dataclass
class _BookingState:
    user_id: str
    slots: list[CalendarSlot] = field(default_factory=list)
    rejections: int = 0
    # Ownership token written as the Redis lock value for ``slots``. Locks
    # are only released/re-validated when the stored value still matches, so
    # an expired-and-reacquired lock is never treated as ours.
    lock_token: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "rejections": self.rejections,
            "slots": [s.to_dict() for s in self.slots],
            "lock_token": self.lock_token,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> _BookingState:
        return cls(
            user_id=str(data.get("user_id") or ""),
            rejections=int(data.get("rejections") or 0),
            slots=[CalendarSlot.from_dict(s) for s in data.get("slots") or []],
            lock_token=str(data.get("lock_token") or ""),
        )


class MeetingBookingService:
    """Drives proposal → soft-lock → confirm → book → CRM sync per thread."""

    def __init__(self, session: AsyncSession, redis_client: Any = None) -> None:
        self.session = session
        self._redis = redis_client
        self.availability = CalendarAvailabilityService(session)

    async def _get_redis(self) -> Any:
        if self._redis is None:
            from app.redis_client import get_redis_client

            self._redis = await get_redis_client()
        return self._redis

    # -- Redis soft-lock (AC-2 / AD-117) ------------------------------------

    @staticmethod
    def slot_lock_key(user_id: str, slot: CalendarSlot) -> str:
        return SLOT_LOCK_KEY_TEMPLATE.format(
            user_id=user_id, slot_timestamp=slot.lock_timestamp()
        )

    @staticmethod
    def pick_owner_credential(
        credentials: list[CalendarCredentials], user_id: str | None
    ) -> CalendarCredentials:
        """Choose the single credential owning the lock namespace (AD-117).

        Prefer the credential whose ``user_id`` matches the caller so a
        multi-calendar workspace locks slots under the AE's own calendar;
        fall back to the first (most recently updated) connector.
        """
        if user_id:
            for cred in credentials:
                if cred.user_id == str(user_id):
                    return cred
        return credentials[0]

    async def soft_lock_slots(
        self,
        user_id: str,
        slots: list[CalendarSlot],
        *,
        token: str | None = None,
    ) -> tuple[list[CalendarSlot], str]:
        """NX-lock each slot for 15 min; returns ``(locked slots, token)``.

        The token is stored as the lock value so later releases can prove
        ownership (see :meth:`release_slot_locks`).
        """
        redis = await self._get_redis()
        token = token or uuid.uuid4().hex
        locked: list[CalendarSlot] = []
        for slot in slots:
            try:
                acquired = await redis.set(
                    self.slot_lock_key(user_id, slot),
                    token,
                    ex=SLOT_LOCK_TTL_SECONDS,
                    nx=True,
                )
            except Exception:
                logger.warning("Soft-lock write failed", exc_info=True)
                acquired = None
            if acquired:
                locked.append(slot)
        return locked, token

    _RELEASE_LOCK_LUA = (
        "if redis.call('get', KEYS[1]) == ARGV[1] then "
        "return redis.call('del', KEYS[1]) else return 0 end"
    )

    async def release_slot_locks(
        self,
        user_id: str,
        slots: list[CalendarSlot],
        token: str | None = None,
    ) -> None:
        """Delete locks only while we still own them (compare-and-delete).

        Without ``token`` nothing is deleted: after TTL expiry another
        conversation may legitimately hold the same key.
        """
        if not slots or not token:
            return
        redis = await self._get_redis()
        for slot in slots:
            try:
                await redis.eval(
                    self._RELEASE_LOCK_LUA,
                    1,
                    self.slot_lock_key(user_id, slot),
                    token,
                )
            except Exception:
                logger.warning("Soft-lock release failed", exc_info=True)

    async def _ensure_slot_lock(
        self,
        user_id: str,
        slot: CalendarSlot,
        token: str | None,
    ) -> bool:
        """Re-acquire or confirm ownership of a slot's soft-lock.

        The state outlives the 15-minute lock TTL, so a confirmed slot may
        have expired (re-acquire with NX) or been taken by another
        conversation (fail - never book on someone else's lock).
        """
        redis = await self._get_redis()
        key = self.slot_lock_key(user_id, slot)
        token = token or uuid.uuid4().hex
        try:
            acquired = await redis.set(
                key, token, ex=SLOT_LOCK_TTL_SECONDS, nx=True
            )
            if acquired:
                return True
            existing = await redis.get(key)
            if existing is not None and str(existing) == token:
                await redis.expire(key, SLOT_LOCK_TTL_SECONDS)
                return True
        except Exception:
            logger.warning("Soft-lock re-validation failed", exc_info=True)
        return False

    # -- conversation state --------------------------------------------------

    def _state_key(self, workspace_id: int, thread_id: str) -> str:
        return STATE_KEY_TEMPLATE.format(
            workspace_id=workspace_id, thread_id=thread_id
        )

    async def _load_state(
        self, workspace_id: int, thread_id: str
    ) -> _BookingState | None:
        redis = await self._get_redis()
        try:
            raw = await redis.get(self._state_key(workspace_id, thread_id))
        except Exception:
            logger.warning("Booking state read failed", exc_info=True)
            return None
        if not raw:
            return None
        import json

        try:
            return _BookingState.from_dict(json.loads(raw))
        except Exception:
            logger.warning("Corrupt booking state for %s", thread_id)
            return None

    async def _save_state(
        self, workspace_id: int, thread_id: str, state: _BookingState
    ) -> None:
        import json

        redis = await self._get_redis()
        try:
            await redis.set(
                self._state_key(workspace_id, thread_id),
                json.dumps(state.to_dict()),
                ex=STATE_TTL_SECONDS,
            )
        except Exception:
            logger.warning("Booking state write failed", exc_info=True)

    async def _clear_state(self, workspace_id: int, thread_id: str) -> None:
        redis = await self._get_redis()
        try:
            await redis.delete(self._state_key(workspace_id, thread_id))
        except Exception:
            logger.warning("Booking state clear failed", exc_info=True)

    # -- booking link (AC-5) -------------------------------------------------

    @staticmethod
    def booking_link(workspace_id: int, lead_id: Any | None = None) -> str:
        base = (
            getattr(config, "MEETING_BOOKING_BASE_URL", None)
            or getattr(config, "NEXT_FRONTEND_URL", None)
            or "https://app.nowing.ai"
        ).rstrip("/")
        path = f"/book/{workspace_id}"
        if lead_id:
            path += f"/{lead_id}"
        return f"{base}{path}"

    # -- main entry point ----------------------------------------------------

    async def handle_turn(
        self,
        workspace_id: int,
        thread_id: str,
        text: str,
        *,
        user_id: str | None = None,
        lead: Any | None = None,
        lead_getter: Any | None = None,
        attendee_email: str | None = None,
    ) -> MeetingTurnResult | None:
        """Advance the booking conversation; ``None`` = not meeting-related."""
        # Without a thread id no state can be persisted, so proposed locks
        # would be orphaned and confirmation impossible - fall through to
        # the normal reply flow instead.
        if not thread_id:
            return None
        state = await self._load_state(workspace_id, thread_id)

        if state is not None and state.slots:
            if lead is None and lead_getter is not None:
                lead = await lead_getter()
            return await self._handle_pending_state(
                workspace_id, thread_id, text, state, lead, attendee_email
            )

        if not detect_meeting_intent(text):
            return None

        # Resolve credentials before touching the CRM so a workspace without a
        # connected calendar simply falls through to the normal reply flow.
        credentials = await self.availability.resolve_credentials(workspace_id)
        if not credentials:
            return None
        if lead is None and lead_getter is not None:
            lead = await lead_getter()
        return await self._propose(
            workspace_id,
            thread_id,
            user_id=user_id,
            lead=lead,
            credentials=credentials,
        )

    async def _handle_pending_state(
        self,
        workspace_id: int,
        thread_id: str,
        text: str,
        state: _BookingState,
        lead: Any | None,
        attendee_email: str | None,
    ) -> MeetingTurnResult | None:
        # An explicit slot choice wins over rejection keywords so that
        # "đổi sang 14:00" confirms the new slot instead of re-proposing.
        choice = parse_slot_choice(text, state.slots)
        if choice is not None:
            return await self._confirm_slot(
                workspace_id, thread_id, state, state.slots[choice], lead,
                attendee_email,
            )

        if detect_slot_rejection(text):
            return await self._handle_rejection(
                workspace_id, thread_id, state, lead
            )

        if detect_generic_confirmation(text):
            if len(state.slots) == 1:
                return await self._confirm_slot(
                    workspace_id,
                    thread_id,
                    state,
                    state.slots[0],
                    lead,
                    attendee_email,
                )
            options = ", ".join(
                f"{i + 1}) {s.label_ict()}"
                for i, s in enumerate(state.slots)
            )
            return MeetingTurnResult(
                reply_text=(
                    "Dạ anh/chị muốn chốt khung giờ nào ạ? "
                    f"Nhắn giúp em số ({options}) nhé ạ."
                ),
                reason="slot_clarification",
            )

        return None

    async def _propose(
        self,
        workspace_id: int,
        thread_id: str,
        *,
        user_id: str | None,
        lead: Any | None,
        credentials: list[CalendarCredentials] | None = None,
        exclude_starts: set[int] | None = None,
        rejections: int = 0,
        prior_state: _BookingState | None = None,
    ) -> MeetingTurnResult | None:
        if credentials is None:
            free, credentials = await self.availability.compute_availability(
                workspace_id
            )
            if not credentials:
                # No calendar connected → let the normal RAG flow answer.
                return None
        else:
            now = datetime.now(VN_TZ)
            time_max = now + timedelta(days=BUSINESS_DAYS + 3)
            busy: list[tuple[datetime, datetime]] = []
            for credential in credentials:
                busy.extend(
                    await self.availability.get_busy_intervals(
                        credential, now, time_max
                    )
                )
            free = compute_free_slots(busy, now=now)
        # One owner credential per flow keeps every lock under a single
        # namespace - the route resolves the same owner when booking.
        owner_id = self.pick_owner_credential(credentials, user_id).user_id
        if exclude_starts:
            free = [
                s for s in free if s.lock_timestamp() not in exclude_starts
            ]
        candidates = select_proposals(free, count=PROPOSAL_COUNT)
        locked, lock_token = await self.soft_lock_slots(owner_id, candidates)

        if prior_state is not None and prior_state.slots:
            # Drop locks for the superseded proposals (only if still ours).
            await self.release_slot_locks(
                prior_state.user_id or owner_id,
                prior_state.slots,
                prior_state.lock_token,
            )

        if not locked:
            link = self.booking_link(
                workspace_id, getattr(lead, "id", None)
            )
            await self._clear_state(workspace_id, thread_id)
            return MeetingTurnResult(
                reply_text=(
                    "Dạ lịch sắp tới của em hơi kín ạ. Anh/chị đặt lịch trực "
                    f"tiếp tại đây giúp em nhé: {link}"
                ),
                reason="no_free_slots",
            )

        if thread_id:
            await self._save_state(
                workspace_id,
                thread_id,
                _BookingState(
                    user_id=owner_id,
                    slots=locked,
                    rejections=rejections,
                    lock_token=lock_token,
                ),
            )

        options = "\n".join(
            f"{i + 1}. {slot.label_ict()}" for i, slot in enumerate(locked)
        )
        return MeetingTurnResult(
            reply_text=(
                "Dạ em xin phép đề xuất vài khung giờ ạ:\n"
                f"{options}\n"
                "Anh/chị chọn khung nào tiện nhất giúp em nhé ạ."
            ),
            reason="slots_proposed",
        )

    async def _confirm_slot(
        self,
        workspace_id: int,
        thread_id: str,
        state: _BookingState,
        slot: CalendarSlot,
        lead: Any | None,
        attendee_email: str | None,
    ) -> MeetingTurnResult:
        if attendee_email is None and lead is not None:
            attendee_email = await self._resolve_attendee_email(lead)
        result = await self.book_slot(
            workspace_id,
            state.user_id,
            slot,
            lead=lead,
            attendee_email=attendee_email,
            lock_token=state.lock_token,
        )
        if result.booked:
            # Release all proposal locks; the booked slot's lock is
            # superseded by the real calendar event.
            await self.release_slot_locks(
                state.user_id, state.slots, state.lock_token
            )
            await self._clear_state(workspace_id, thread_id)
            return result

        # Failed booking: drop the picked slot's lock so the slot is not
        # blocked for other conversations; remaining proposals stay locked.
        await self.release_slot_locks(state.user_id, [slot], state.lock_token)
        return MeetingTurnResult(
            reply_text=(
                "Dạ em chưa đặt được lịch vào lúc này ạ. Anh/chị để em "
                "chuyển chuyên viên phụ trách hỗ trợ đặt lịch ngay nhé."
            ),
            reason="booking_failed",
        )

    async def _handle_rejection(
        self,
        workspace_id: int,
        thread_id: str,
        state: _BookingState,
        lead: Any | None,
    ) -> MeetingTurnResult:
        state.rejections += 1
        if state.rejections >= MAX_NEGOTIATION_TURNS:
            return await self._escalate(workspace_id, thread_id, state, lead)

        exclude = {s.lock_timestamp() for s in state.slots}
        result = await self._propose(
            workspace_id,
            thread_id,
            user_id=state.user_id,
            lead=lead,
            exclude_starts=exclude,
            rejections=state.rejections,
            prior_state=state,
        )
        if result is None:
            # Re-proposal aborted (e.g. credentials vanished mid-flow) - the
            # incremented rejection count must persist or the escalation
            # limit can never fire.
            await self._save_state(workspace_id, thread_id, state)
            return MeetingTurnResult(
                reply_text=(
                    "Dạ em ghi nhận ạ. Anh/chị cho em xin khung giờ khác "
                    "tiện cho mình nhé."
                ),
                reason="rejected_no_calendar",
            )
        return result

    async def _escalate(
        self,
        workspace_id: int,
        thread_id: str,
        state: _BookingState,
        lead: Any | None,
    ) -> MeetingTurnResult:
        """AC-5: after 2 rejected turns → booking link + human takeover tag."""
        await self.release_slot_locks(
            state.user_id, state.slots, state.lock_token
        )
        await self._clear_state(workspace_id, thread_id)

        if lead is not None:
            await self._tag_human_takeover(lead)
        if thread_id:
            try:
                from app.services.auto_reply_agent import pause_auto_reply

                await pause_auto_reply(thread_id)
            except Exception:
                # A silently-skipped takeover leaves the bot replying while
                # the AE thinks a human stepped in - worth a warning.
                logger.warning(
                    "Could not pause auto-reply on escalation", exc_info=True
                )

        link = self.booking_link(workspace_id, getattr(lead, "id", None))
        return MeetingTurnResult(
            reply_text=(
                "Dạ anh/chị đặt lịch trực tiếp tại đây giúp em nhé ạ: "
                f"{link}. Chuyên viên bên em sẽ liên hệ hỗ trợ thêm ạ."
            ),
            escalated=True,
            reason="negotiation_limit",
        )

    async def _tag_human_takeover(self, lead: Any) -> None:
        """Append the ``human_takeover_needed`` tag to the lead timeline."""
        try:
            from app.db import LeadActivityLog

            details = dict(getattr(lead, "details", None) or {})
            log = LeadActivityLog(
                workspace_id=lead.workspace_id,
                lead_id=lead.id,
                activity_type="tag_added",
                title=f"Gắn tag {HUMAN_TAKEOVER_TAG}",
                details={
                    "tags": [HUMAN_TAKEOVER_TAG],
                    "reason": "meeting_negotiation_exhausted",
                    **({"context": details} if details else {}),
                },
            )
            self.session.add(log)
        except Exception:
            logger.warning("Failed to tag human_takeover_needed", exc_info=True)

    async def _resolve_attendee_email(self, lead: Any) -> str | None:
        """Best-effort prospect email for the calendar invite (AC-4)."""
        try:
            from app.db import VerifiedContact

            stmt = (
                select(VerifiedContact)
                .where(
                    VerifiedContact.lead_id == lead.id,
                    VerifiedContact.workspace_id == lead.workspace_id,
                    VerifiedContact.consent.is_(True),
                    VerifiedContact.is_valid.is_(True),
                    VerifiedContact.email.is_not(None),
                )
                .order_by(VerifiedContact.confidence.desc())
                .limit(1)
            )
            contact = (
                await self.session.execute(stmt)
            ).scalars().first()
            email = getattr(contact, "email", None) if contact else None
            if not isinstance(email, str) or not email:
                return None
            # PII may be encrypted at rest (AD-42/49) - never send ciphertext
            # as an invitee address.
            try:
                from app.services.pii.verified_contact_encryption import (
                    VerifiedContactEncryption,
                )

                enc = VerifiedContactEncryption()
                if enc.is_encrypted(email):
                    email = enc.decrypt(email)
            except Exception:
                logger.debug("Attendee email decrypt failed", exc_info=True)
            return email if "@" in email else None
        except Exception:
            logger.debug("Attendee email resolution failed", exc_info=True)
            return None

    # -- booking + CRM sync (AC-4) -------------------------------------------

    async def book_slot(
        self,
        workspace_id: int,
        user_id: str,
        slot: CalendarSlot,
        *,
        lead: Any | None = None,
        attendee_email: str | None = None,
        summary: str | None = None,
        credentials: list[CalendarCredentials] | None = None,
        lock_token: str | None = None,
    ) -> MeetingTurnResult:
        """Create the calendar event and sync CRM status.

        The Redis state outlives the 15-minute lock TTL, so the slot is
        re-validated first: it must still be in the future and its
        soft-lock must be ours (or re-acquirable via SET NX).
        """
        if slot.start <= datetime.now(UTC):
            return MeetingTurnResult(reply_text="", reason="slot_past")

        if credentials is None:
            credentials = await self.availability.resolve_credentials(
                workspace_id
            )
        if not credentials:
            return MeetingTurnResult(
                reply_text="", reason="no_credentials"
            )

        # Book on the credential that owns the lock namespace when possible.
        credential = next(
            (c for c in credentials if c.user_id == str(user_id)),
            credentials[0],
        )

        if not await self._ensure_slot_lock(user_id, slot, lock_token):
            return MeetingTurnResult(reply_text="", reason="lock_lost")

        event_summary = summary or "Cuộc hẹn tư vấn Nowing"
        try:
            event_id, meeting_link = await self.availability.create_event(
                credential,
                summary=event_summary,
                start=slot.start,
                end=slot.end,
                attendee_email=attendee_email,
                description=(
                    "Lịch hẹn được đặt tự động bởi Nowing Auto-Reply."
                ),
            )
        except Exception:
            logger.warning(
                "Calendar event creation failed provider=%s",
                credential.provider,
                exc_info=True,
            )
            return MeetingTurnResult(reply_text="", reason="create_failed")

        if not event_id:
            # Provider returned no event - never mark the CRM for a phantom.
            logger.warning(
                "Calendar create_event returned no event_id provider=%s",
                credential.provider,
            )
            return MeetingTurnResult(reply_text="", reason="create_failed")

        if lead is not None:
            await self._sync_crm_meeting_scheduled(
                lead, slot, event_id=event_id, meeting_link=meeting_link
            )

        link_text = f" Link tham gia: {meeting_link}" if meeting_link else ""
        if attendee_email:
            invite_text = "Thư mời đã được gửi qua lịch của anh/chị rồi ạ."
        else:
            invite_text = "Em sẽ gửi thông tin chi tiết cho anh/chị ngay ạ."
        return MeetingTurnResult(
            reply_text=(
                f"Dạ em đã đặt lịch hẹn {slot.label_ict()} ạ.{link_text} "
                f"{invite_text}"
            ),
            booked=True,
            slot=slot,
            event_id=event_id,
            meeting_link=meeting_link,
        )

    async def _sync_crm_meeting_scheduled(
        self,
        lead: Any,
        slot: CalendarSlot,
        *,
        event_id: str | None,
        meeting_link: str | None,
    ) -> None:
        """AC-4: Lead.status → ``meeting_scheduled`` + pipeline stage + log."""
        from app.db import LeadActivityLog, LeadPipelineStage

        try:
            stage_stmt = select(LeadPipelineStage).where(
                LeadPipelineStage.workspace_id == lead.workspace_id,
                LeadPipelineStage.slug == MEETING_SCHEDULED_STATUS,
            )
            stage = (
                await self.session.execute(stage_stmt)
            ).scalars().first()
            if stage is not None:
                lead.stage_id = stage.id

            lead.status = MEETING_SCHEDULED_STATUS
            lead.version = (lead.version or 0) + 1

            self.session.add(
                LeadActivityLog(
                    workspace_id=lead.workspace_id,
                    lead_id=lead.id,
                    activity_type="meeting_scheduled",
                    title=f"Đặt lịch hẹn {slot.label_ict()}",
                    details={
                        "slot_start_utc": slot.start.astimezone(UTC).isoformat(),
                        "slot_end_utc": slot.end.astimezone(UTC).isoformat(),
                        "slot_label_ict": slot.label_ict(),
                        "event_id": event_id,
                        "meeting_link": meeting_link,
                        "source": "auto_reply_meeting_booking",
                    },
                )
            )
            await self.session.flush()
        except Exception:
            logger.warning(
                "CRM sync to meeting_scheduled failed for lead %s",
                getattr(lead, "id", None),
                exc_info=True,
            )
