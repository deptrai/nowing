"""Deterministic Vietnam cultural honorific & relationship tone engine (Story 37.2 / AD-116).

Zero-LLM, zero-latency resolution of the Vietnamese honorific pronoun pair used
when addressing a prospect (``Anh`` / ``Chị`` / ``Em`` / ``Quý đối tác``) versus
the sender's own pronoun (``Em`` / ``Anh`` / ``Chị`` / ``Chúng tôi``).

Rules (AD-116):
- Age differential is inferred deterministically from birth year (CCCD or
  explicit field) or graduation year (~22 at graduation).
- Title seniority (C-level / Trưởng / Giám đốc vs intern / nhân viên) feeds the
  same hierarchy decision.
- Foreign names or international domains default to English business
  honorifics (``Dear Mr./Ms. [Lastname]``).
- Ambiguous demographics fall back to ``Quý anh/chị`` or ``Quý đối tác``.
- Robotic direct translations (``Bạn``/``Tôi``) are rejected by
  :class:`HonorificQualityGate`.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.config import config

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _strip_diacritics(text: str) -> str:
    """NFD + Mn-mark strip — same normalize pattern as platform scrapers."""
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------------------
# Anti-translation quality gate (AC-3)
# ---------------------------------------------------------------------------

# Matched on accent-stripped lowercase text so diacritic-less machine output
# ("ban", "toi") is still caught.
# - "ban" is only flagged in second-person address contexts ("chao ban",
#   "ban oi/co/se...") — legit compounds like "ban giám đốc", "ban tổ chức"
#   are allowed.
# - "toi" is a robotic self-reference — but legit phrases ("chúng tôi",
#   "của tôi", "theo tôi", "với tôi", "cho tôi", "bên tôi", "phía tôi") are
#   excluded via fixed-width lookbehinds on normalized text.
ROBOTIC_PRONOUN_RE = re.compile(
    r"(?:chao|thua|cam on|gui|xin|cho|nho|voi|hen|moi)\s+ban\b"
    r"|\bban\s+(?:oi|a|nhe|nha|vay|nhi|ha|sao|co|da|se|can|muon|dang|van|la|duoc|khong|the|nay|kia|do|ay)\b"
    r"|(?<!chung )(?<!cua )(?<!theo )(?<!voi )(?<!cho )(?<!ben )(?<!phia )(?<!cua rieng )\btoi\b"
)


class HonorificQualityGate:
    """Rejects robotic direct translations such as 'Bạn'/'Tôi' (AC-3)."""

    @classmethod
    def is_robotic(cls, text: str | None) -> bool:
        """True when the text uses machine-translated pronouns."""
        if not text:
            return False
        normalized = _strip_diacritics(text).lower()
        return bool(ROBOTIC_PRONOUN_RE.search(normalized))

    @classmethod
    def is_acceptable(cls, text: str | None) -> bool:
        return not cls.is_robotic(text)


# ---------------------------------------------------------------------------
# Resolution result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HonorificResolution:
    """Resolved addressing tuple for one prospect."""

    salutation: str
    prospect_pronoun: str
    sender_pronoun: str
    tone: str = "vi"  # "vi" (Vietnamese) | "en" (English business)
    reason: str = ""
    contact_name: str | None = None
    prospect_birth_year: int | None = None

    def to_context_vars(self) -> dict[str, str]:
        """Template/LLM context variables — ``{salutation}`` token (AC-2)."""
        return {
            "salutation": self.salutation,
            "prospect_pronoun": self.prospect_pronoun,
            "sender_pronoun": self.sender_pronoun,
            "honorific_tone": self.tone,
            "honorific_reason": self.reason,
        }

    def prompt_directive(self) -> str:
        """Single deterministic pronoun directive for LLM system prompts."""
        if self.tone == "en":
            return (
                f'Address the prospect in English business tone as '
                f'"{self.salutation}" and sign off as "{self.sender_pronoun}".'
            )
        return (
            f'Xưng hô với khách hàng là "{self.prospect_pronoun}" '
            f'(chào "{self.salutation}"), tự xưng "{self.sender_pronoun}".'
        )


NEUTRAL_RESOLUTION = HonorificResolution(
    salutation="Quý đối tác",
    prospect_pronoun="Quý đối tác",
    sender_pronoun="Chúng tôi",
    tone="vi",
    reason="fallback_neutral",
)


async def workspace_sender_demographics(
    session: AsyncSession, workspace_id: int
) -> tuple[int | None, str | None]:
    """Per-workspace sender profile — overrides the global env defaults.

    Reads ``sequencer_sender_birth_year`` / ``sequencer_sender_gender``
    from ``workspaces.icp_criteria`` (the existing workspace settings
    bag). Returns ``(None, None)`` when unset so callers keep the global
    ``SEQUENCER_SENDER_*`` fallbacks inside ``resolve()``.
    """
    try:
        from app.db import Workspace

        workspace = await session.get(Workspace, workspace_id)
        settings = getattr(workspace, "icp_criteria", None)
        if not isinstance(settings, dict):
            return None, None
        raw_year = settings.get("sequencer_sender_birth_year")
        birth_year = None
        if raw_year is not None:
            try:
                birth_year = int(str(raw_year).strip())
            except (TypeError, ValueError):
                birth_year = None
        gender = settings.get("sequencer_sender_gender")
        return birth_year, gender if isinstance(gender, str) else None
    except Exception:  # settings read must never block dispatch
        logger.debug("workspace sender demographics read failed", exc_info=True)
        return None, None


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


class VietnamHonorificResolver:
    """Deterministic honorific resolver (0ms latency, $0 token cost — AD-116)."""

    # Title keywords → seniority signal (matched on lowercase substring).
    SENIOR_TITLE_KEYWORDS = (
        "ceo", "cto", "cfo", "coo", "chief",
        "giám đốc", "giam doc", "tổng giám đốc", "tong giam doc",
        "chủ tịch", "chu tich", "phó chủ tịch",
        "founder", "co-founder", "owner", "chủ doanh nghiệp", "chu doanh nghiep",
        "director", "trưởng", "truong", "head of", "head",
        "manager", "quản lý", "quan ly", "partner", "principal",
    )
    JUNIOR_TITLE_KEYWORDS = (
        "intern", "thực tập", "thuc tap", "trainee", "fresher", "junior",
        "nhân viên", "nhan vien", "staff", "trợ lý", "tro ly", "assistant",
        "cộng tác viên", "cong tac vien",
    )

    # Common Vietnamese surnames — presence of any token marks the name as VN.
    VN_SURNAMES = frozenset({
        "nguyen", "nguyễn", "tran", "trần", "le", "lê", "pham", "phạm",
        "hoang", "hoàng", "huynh", "huỳnh", "phan", "phùng", "phung",
        "vu", "vũ", "võ", "vo", "dang", "đặng", "bui", "bùi",
        "do", "đỗ", "đo", "ho", "hồ", "ngo", "ngô", "duong", "dương",
        "ly", "lý", "truong", "trương", "dinh", "đinh", "luong", "lương",
        "cao", "mai", "ta", "tạ", "thai", "thái", "lam", "lâm", "chu",
        "ha", "hà", "trinh", "trịnh", "dao", "đào", "ton", "tôn",
        "quach", "quách", "diep", "diệp", "kieu", "kiều", "nong", "nông",
        "ong", "ông", "thach", "thạch", "tang", "tăng", "to", "tô",
        "vien", "viên", "vuong", "vương", "doan", "đoàn",
    })

    # Strong gender markers in Vietnamese MIDDLE names (index 1..-1).
    FEMALE_NAME_MARKERS = frozenset({
        "thị", "thi", "kim", "ngọc", "ngoc", "hồng", "hong",
        "phương", "phuong", "quỳnh", "quynh", "thu", "thủy", "thuy",
        "mỹ", "my", "như", "nhu", "trúc", "truc", "tuyết", "tuyet",
    })
    MALE_NAME_MARKERS = frozenset({
        "văn", "van", "hữu", "huu", "đức", "duc", "công", "cong",
        "quốc", "quoc", "hùng", "hung", "trung", "đình", "dinh",
    })

    _VN_DIACRITICS_RE = re.compile(
        r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩị"
        r"óòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
        re.IGNORECASE,
    )
    _CCCD_RE = re.compile(r"\b\d{12}\b")
    _YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")

    # A prospect this many years younger than the sender is addressed as "Em".
    YOUNGER_THRESHOLD_YEARS = 5
    # Estimated age at university graduation for birth-year inference.
    GRADUATION_AGE = 22

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(
        self,
        *,
        lead: Any | None = None,
        contact: Any | None = None,
        profile: dict[str, Any] | None = None,
        sender_birth_year: int | None = None,
        sender_gender: str | None = None,
    ) -> HonorificResolution:
        """Resolve the (prospect, sender) honorific pair for a prospect.

        Deterministic rules only — never calls an LLM (AD-116).
        """
        if sender_birth_year is None:
            sender_birth_year = getattr(
                config, "SEQUENCER_SENDER_BIRTH_YEAR", None
            )
        if sender_gender is None:
            sender_gender = getattr(config, "SEQUENCER_SENDER_GENDER", None)
        sender_gender = self._normalize_gender(sender_gender)

        data = self._collect(lead=lead, contact=contact, profile=profile)
        name = data.get("name")

        # Foreign prospects / international domains → English business tone.
        if self._is_foreign(data, name):
            return self._resolve_english(data, name)

        birth_year, cccd_gender = self._infer_birth_year(data)
        gender = self._infer_gender(data, name, cccd_gender)
        given = self._vietnamese_given_name(name)

        if not name or not given:
            # Company-level outreach without a person name.
            return HonorificResolution(
                salutation="Quý đối tác",
                prospect_pronoun="Quý đối tác",
                sender_pronoun="Chúng tôi",
                tone="vi",
                reason="no_contact_name",
                contact_name=name,
                prospect_birth_year=birth_year,
            )

        if gender is None:
            # Ambiguous demographics → neutral professional phrasing.
            salutation = f"Quý anh/chị {given}"
            return HonorificResolution(
                salutation=salutation,
                prospect_pronoun="Quý anh/chị",
                sender_pronoun="Chúng tôi",
                tone="vi",
                reason="ambiguous_gender",
                contact_name=name,
                prospect_birth_year=birth_year,
            )

        senior = self._is_senior_title(data.get("title"))
        junior = self._is_junior_title(data.get("title"))

        age_diff = None  # >0 ⇒ prospect is older than the sender
        if birth_year and sender_birth_year:
            age_diff = int(sender_birth_year) - birth_year

        prospect_clearly_younger = (
            junior or (age_diff is not None and age_diff <= -self.YOUNGER_THRESHOLD_YEARS)
        )

        if prospect_clearly_younger and not senior:
            sender_pronoun = "Chị" if sender_gender == "female" else "Anh"
            return HonorificResolution(
                salutation=f"Em {given}",
                prospect_pronoun="Em",
                sender_pronoun=sender_pronoun,
                tone="vi",
                reason="prospect_younger_or_junior",
                contact_name=name,
                prospect_birth_year=birth_year,
            )

        # Default: customer respect — prospect addressed as Anh/Chị, sender "Em".
        prospect_pronoun = "Anh" if gender == "male" else "Chị"
        reason = "senior_title" if senior else (
            "prospect_older" if age_diff is not None and age_diff > 0
            else "customer_respect_default"
        )
        return HonorificResolution(
            salutation=f"{prospect_pronoun} {given}",
            prospect_pronoun=prospect_pronoun,
            sender_pronoun="Em",
            tone="vi",
            reason=reason,
            contact_name=name,
            prospect_birth_year=birth_year,
        )

    # ------------------------------------------------------------------
    # Field collection (defensive — ORM objects, dicts, MagicMocks)
    # ------------------------------------------------------------------

    @staticmethod
    def _text(value: Any) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @staticmethod
    def _mapping(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _collect(
        self,
        *,
        lead: Any | None,
        contact: Any | None,
        profile: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Merge into one flat mapping; later sources overwrite earlier ones.

        Precedence: ``profile`` > ``contact`` > ``lead`` — contact-level PII
        (name/title/email/phone) is the most reliable, so contact values
        overwrite whatever the lead row supplied for the same key.
        """
        data: dict[str, Any] = {}

        lead_cf = self._mapping(getattr(lead, "custom_fields", None)) if lead else {}
        lead_extra = self._mapping(getattr(lead, "extra_data", None)) if lead else {}
        contact_extra = (
            self._mapping(getattr(contact, "external_chat_ids", None))
            if contact
            else {}
        )

        def _put(key: str, *candidates: Any) -> None:
            # Last-write-wins across successive _put calls; within one call the
            # first non-empty candidate wins.
            for cand in candidates:
                text = self._text(cand)
                if text is not None:
                    data[key] = text
                    return

        # Lead-level signals (lowest precedence).
        if lead:
            _put(
                "name",
                getattr(lead, "contact_name", None),
                lead_cf.get("contact_name"),
                lead_cf.get("name"),
                getattr(lead, "legal_representative", None),
            )
            _put("domain", getattr(lead, "domain", None), lead_cf.get("domain"))
            _put("tax_id", getattr(lead, "tax_id", None), lead_cf.get("tax_id"))
            for key in (
                "title", "job_title", "gender", "birth_year", "year_of_birth",
                "graduation_year", "cccd", "id_number", "national_id", "mst",
                "nationality", "country", "email", "phone",
            ):
                _put(key, lead_cf.get(key), lead_extra.get(key))

        # Contact-level signals.
        if contact:
            _put("name", getattr(contact, "name", None))
            _put("title", getattr(contact, "title", None))
            _put("email", getattr(contact, "email", None))
            _put("phone", getattr(contact, "phone", None))
            for key in ("gender", "birth_year", "cccd", "nationality", "country"):
                _put(key, contact_extra.get(key))

        # Explicit caller profile wins.
        for key, value in self._mapping(profile).items():
            text = self._text(value) if not isinstance(value, int) else value
            if text is not None:
                data[key] = text

        return data

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _is_senior_title(self, title: str | None) -> bool:
        if not title:
            return False
        lowered = title.lower()
        return any(kw in lowered for kw in self.SENIOR_TITLE_KEYWORDS)

    def _is_junior_title(self, title: str | None) -> bool:
        if not title:
            return False
        lowered = title.lower()
        return any(kw in lowered for kw in self.JUNIOR_TITLE_KEYWORDS)

    def _looks_vietnamese(self, name: str | None) -> bool:
        if not name:
            return False
        if self._VN_DIACRITICS_RE.search(name):
            return True
        tokens = [t.lower() for t in name.split() if t]
        return any(t in self.VN_SURNAMES for t in tokens)

    # Free-mail providers are NOT a foreign signal — gmail is dominant in VN.
    FREE_MAIL_DOMAINS = frozenset({
        "gmail.com", "googlemail.com", "outlook.com", "hotmail.com",
        "live.com", "icloud.com", "me.com", "msn.com", "aol.com",
        "proton.me", "protonmail.com", "gmx.com", "mail.com",
        "yandex.com", "yandex.ru",
    })
    VN_NATIONALITIES = frozenset({
        "vietnam", "việt nam", "viet nam", "vn", "vnm",
        "vietnamese", "vi", "việt",
    })

    @staticmethod
    def _domain_host(domain_or_email: str | None) -> str | None:
        if not domain_or_email:
            return None
        host = domain_or_email.split("@")[-1].strip().lower()
        return host if "." in host else None

    def _is_free_mail(self, host: str | None) -> bool:
        if not host:
            return False
        if host in self.FREE_MAIL_DOMAINS:
            return True
        # yahoo.* regional domains (yahoo.com.vn, yahoo.co.uk, ...)
        return host == "yahoo" or host.startswith("yahoo.")

    def _is_foreign(self, data: dict[str, Any], name: str | None) -> bool:
        nationality = (data.get("nationality") or data.get("country") or "").lower()
        if nationality:
            return nationality not in self.VN_NATIONALITIES

        host = self._domain_host(data.get("domain") or data.get("email"))
        if host and (host == "vn" or host.endswith(".vn")):
            return False  # domestic signal
        if self._looks_vietnamese(name):
            return False
        if not name:
            return False
        # Only a non-.vn corporate/domestic domain counts as foreign evidence;
        # free-mail (gmail dominant in VN) and absent domains do not.
        return bool(host and not self._is_free_mail(host))

    def _infer_birth_year(
        self, data: dict[str, Any]
    ) -> tuple[int | None, str | None]:
        """Return (birth_year, gender_hint) from explicit/CCCD/graduation data."""
        current_year = datetime.now(UTC).year

        def _sane(year: int) -> int | None:
            return year if 1920 <= year <= current_year else None

        for key in ("birth_year", "year_of_birth"):
            raw = data.get(key)
            try:
                year = int(str(raw).strip())
            except (TypeError, ValueError):
                continue
            sane = _sane(year)
            if sane:
                return sane, None

        # CCCD (12 digits): digit 4 = century+gender code, digits 5-6 = YY.
        for key in ("cccd", "id_number", "national_id"):
            raw = data.get(key)
            if not raw:
                continue
            match = self._CCCD_RE.search(str(raw))
            if match:
                digits = match.group(0)
                century_code = int(digits[3])
                century = 1900 + (century_code // 2) * 100
                year = _sane(century + int(digits[4:6]))
                if year:
                    return year, "female" if century_code % 2 else "male"
            # Fallback: embedded 4-digit year ("CCCD ... SN 1985").
            year_match = self._YEAR_RE.search(str(raw))
            if year_match:
                sane = _sane(int(year_match.group(1)))
                if sane:
                    return sane, None

        # NOTE: mst/tax_id are deliberately NOT scanned — a Vietnamese tax code
        # is an organization identifier and does not encode a person's birth
        # year.

        grad = data.get("graduation_year")
        if grad:
            try:
                grad_year = int(str(grad).strip())
            except (TypeError, ValueError):
                grad_year = 0
            if 1950 <= grad_year <= current_year:
                return _sane(grad_year - self.GRADUATION_AGE), None

        return None, None

    _GENDER_MALE = frozenset({"male", "m", "nam", "anh", "mr", "mr."})
    _GENDER_FEMALE = frozenset({
        "female", "f", "nữ", "nu", "chị", "chi", "ms", "ms.", "mrs", "mrs.",
    })

    @classmethod
    def _normalize_gender(cls, raw: Any) -> str | None:
        """Map free-text gender synonyms to ``"male"``/``"female"``/None."""
        if not isinstance(raw, str):
            return None
        value = raw.strip().lower()
        if value in cls._GENDER_MALE:
            return "male"
        if value in cls._GENDER_FEMALE:
            return "female"
        return None

    def _infer_gender(
        self,
        data: dict[str, Any],
        name: str | None,
        cccd_gender: str | None = None,
    ) -> str | None:
        inferred = self._normalize_gender(data.get("gender"))
        if inferred:
            return inferred
        if cccd_gender:
            return cccd_gender
        if name:
            tokens = [t.lower() for t in name.split()]
            middle = tokens[1:-1] if len(tokens) > 2 else []
            if any(t in self.FEMALE_NAME_MARKERS for t in middle):
                return "female"
            if any(t in self.MALE_NAME_MARKERS for t in middle):
                return "male"
        return None

    @staticmethod
    def _vietnamese_given_name(name: str | None) -> str | None:
        """Vietnamese names place the given name last: 'Nguyễn Văn Minh' → 'Minh'."""
        if not name:
            return None
        tokens = name.split()
        return tokens[-1] if tokens else None

    # ------------------------------------------------------------------
    # English business fallback (AC-3)
    # ------------------------------------------------------------------

    def _resolve_english(
        self, data: dict[str, Any], name: str | None
    ) -> HonorificResolution:
        if not name:
            return HonorificResolution(
                salutation="Dear Sir/Madam",
                prospect_pronoun="Mr./Ms.",
                sender_pronoun="We",
                tone="en",
                reason="foreign_no_name",
                contact_name=None,
            )
        tokens = name.split()
        last = tokens[-1]
        gender = self._infer_gender(data, name, None)
        if gender == "male":
            salutation, pronoun = f"Dear Mr. {last}", "Mr."
        elif gender == "female":
            salutation, pronoun = f"Dear Ms. {last}", "Ms."
        else:
            salutation, pronoun = f"Dear Mr./Ms. {last}", "Mr./Ms."
        return HonorificResolution(
            salutation=salutation,
            prospect_pronoun=pronoun,
            sender_pronoun="We",
            tone="en",
            reason="foreign_contact",
            contact_name=name,
        )


__all__ = [
    "NEUTRAL_RESOLUTION",
    "ROBOTIC_PRONOUN_RE",
    "HonorificQualityGate",
    "HonorificResolution",
    "VietnamHonorificResolver",
]
