"""Voice AI SDR Billing, Realtime Metering & QA Scorecard (Story 38.8).

Implements telecom-standard unit economics and post-call CRM sync:
1. 6s + 1s Block Billing: First 6 seconds is billed as 1 block (6s); each
   subsequent second is billed per second. Unit price: 2,500 VND/minute
   (2,500,000 micros/minute = 41,666.67 micros/second).
2. Hang-up Protection: 100% free if call < 10.0s and campaign short-call quota
   <= 15%. Soft-locked deposit is released in full.
3. 2-Phase Commit Wallet Reconciliation:
   - commit_reserved_credit() for actual incurred cost.
   - release_credit() for the remaining reserved deposit balance.
4. BANT Scorecard: Evaluates Budget (0-25), Authority (0-25), Need (0-25),
   Timeline (0-25) -> total score in [0, 100].
5. CRM Sync: Writes interaction log to LeadActivityLog (activity_type="voice_call").
"""

from __future__ import annotations

import asyncio
import logging
import math
import unicodedata
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.voice import (
    VOICE_HANGUP_PROTECTION_MAX_QUOTA,
    VOICE_HANGUP_PROTECTION_SECONDS,
    VOICE_RATE_PER_MINUTE_MICROS,
)
from app.lead_intelligence.dnc.service import get_redis
from app.models.leads.main import LeadActivityLog
from app.services.wallet_credit import commit_reserved_credit, release_credit

logger = logging.getLogger(__name__)

# BANT heuristic keyword patterns (Vietnamese)
_BUDGET_KEYWORDS = (
    "ngân sách",
    "ngan sach",
    "chi phí",
    "chi phi",
    "giá cả",
    "gia ca",
    "báo giá",
    "bao gia",
    "khoảng bao nhiêu",
    "khoang bao nhieu",
    "bao nhiêu tiền",
    "bao nhieu tien",
    "triệu",
    "trieu",
    "kinh phí",
    "kinh phi",
)

_AUTHORITY_KEYWORDS = (
    "giám đốc",
    "giam doc",
    "chủ doanh nghiệp",
    "chu doanh nghiep",
    "tổng giám đốc",
    "tong giam doc",
    "quản lý",
    "quan ly",
    "trưởng phòng",
    "truong phong",
    "anh quyết",
    "anh quyet",
    "chị quyết",
    "chi quyet",
    "để anh xem",
    "de anh xem",
    "người đại diện",
    "nguoi dai dien",
    "founder",
    "ceo",
)

_NEED_KEYWORDS = (
    "đang cần",
    "dang can",
    "đang tìm",
    "dang tim",
    "quan tâm",
    "quan tam",
    "có nhu cầu",
    "co nhu cau",
    "khó khăn",
    "kho khan",
    "bất cập",
    "bat cap",
    "muốn tìm hiểu",
    "muon tim hieu",
    "giải pháp",
    "giai phap",
    "tối ưu",
    "toi uu",
)

_TIMELINE_KEYWORDS = (
    "tuần này",
    "tuan nay",
    "tuần sau",
    "tuan sau",
    "thứ hai",
    "thu hai",
    "thứ ba",
    "thu ba",
    "thứ tư",
    "thu tu",
    "thứ năm",
    "thu nam",
    "thứ sáu",
    "thu sau",
    "hôm nay",
    "hom nay",
    "ngày mai",
    "ngay mai",
    "sớm",
    "som",
    "ngay",
    "trong tháng",
    "trong thang",
    "quý này",
    "quy nay",
    "lúc mấy giờ",
    "luc may gio",
    "hẹn",
    "hen",
    "gặp",
    "gap",
)


def calculate_telecom_block_charge(
    duration_seconds: float,
    rate_per_minute_micros: int = VOICE_RATE_PER_MINUTE_MICROS,
) -> tuple[int, int]:
    """Calculate billed duration and charge under Vietnam telecom block 6s + 1s standard.

    Rules:
    - Duration <= 0: 0 seconds, 0 cost.
    - Duration <= 6.0s: Billed as exactly 6 seconds.
    - Duration > 6.0s: Billed as 6s + ceil(duration - 6s) * 1s.
    - Cost: round(billed_seconds * (rate_per_minute_micros / 60)).

    Returns:
        tuple[billed_seconds, cost_micros]
    """
    if duration_seconds <= 0.0:
        return 0, 0

    if duration_seconds <= 6.0:
        billed_seconds = 6
    else:
        additional_seconds = math.ceil(duration_seconds - 6.0)
        billed_seconds = 6 + additional_seconds

    cost_per_second = rate_per_minute_micros / 60.0
    cost_micros = round(billed_seconds * cost_per_second)

    return billed_seconds, cost_micros


async def evaluate_hangup_protection(
    campaign_id: str | int | None,
    duration_seconds: float,
    *,
    protection_seconds: float = VOICE_HANGUP_PROTECTION_SECONDS,
    max_quota_ratio: float = VOICE_HANGUP_PROTECTION_MAX_QUOTA,
) -> bool:
    """Return True if call qualifies for 100% Hang-up Protection waiver.

    Condition:
    1. Call duration < protection_seconds (10.0s).
    2. Campaign's historical short call ratio <= max_quota_ratio (15%).
       If campaign_id is None, defaults to True (fail-safe protection).
    """
    if duration_seconds >= protection_seconds:
        return False

    if campaign_id is None:
        return True

    redis_client = get_redis()
    if redis_client is None:
        return True  # Fail-safe waiver if Redis is down

    key = f"voice:campaign:metrics:{campaign_id}"
    try:
        metrics = await redis_client.hgetall(key)
        total = int(metrics.get("total_calls", 0))
        short = int(metrics.get("short_calls", 0))

        if total == 0:
            return True

        short_ratio = short / total
        return short_ratio <= max_quota_ratio
    except Exception as exc:
        logger.warning(
            "[HangupProtection] Redis query failed for campaign %s: %s — waiving",
            campaign_id,
            exc,
        )
        return True


async def finalize_call_billing(
    session: AsyncSession,
    user_id: str | UUID,
    reserved_micros: int,
    actual_cost_micros: int,
) -> int:
    """Execute 2-phase commit reconciliation on the user's credit wallet.

    1. If actual_cost_micros > 0: commit actual cost from reserved balance.
    2. Release any remaining reserved deposit back to spendable balance.
    3. If actual_cost_micros == 0: release entire reserved balance.

    Returns:
        The amount of credit committed in micros.
    """
    if reserved_micros <= 0:
        return 0

    cost_to_commit = min(actual_cost_micros, reserved_micros)
    refund_to_release = reserved_micros - cost_to_commit

    if cost_to_commit > 0:
        await commit_reserved_credit(session, user_id, cost_to_commit)
        logger.info(
            "[VoiceBilling] Committed %s micros for user=%s",
            cost_to_commit,
            user_id,
        )

    if refund_to_release > 0:
        await release_credit(session, user_id, refund_to_release)
        logger.info(
            "[VoiceBilling] Released unused deposit %s micros for user=%s",
            refund_to_release,
            user_id,
        )

    return cost_to_commit


def _evaluate_bant_score_keywords(
    transcript: str,
    call_metadata: dict[str, Any] | None = None,
) -> tuple[int, dict[str, int]]:
    """Keyword heuristic fallback for BANT scoring."""
    if not transcript or not transcript.strip():
        return 0, {"budget": 0, "authority": 0, "need": 0, "timeline": 0}

    norm = unicodedata.normalize("NFC", transcript).lower()

    # Budget (0 or 25)
    b_score = 25 if any(k in norm for k in _BUDGET_KEYWORDS) else 0

    # Authority (0 or 25)
    a_score = 25 if any(k in norm for k in _AUTHORITY_KEYWORDS) else 0

    # Need (0 or 25)
    n_score = 25 if any(k in norm for k in _NEED_KEYWORDS) else 0

    # Timeline (0 or 25)
    t_score = 25 if any(k in norm for k in _TIMELINE_KEYWORDS) else 0

    total = b_score + a_score + n_score + t_score
    breakdown = {
        "budget": b_score,
        "authority": a_score,
        "need": n_score,
        "timeline": t_score,
    }
    return total, breakdown


async def aevaluate_bant_score(
    transcript: str,
    call_metadata: dict[str, Any] | None = None,
    *,
    session: AsyncSession | None = None,
    workspace_id: int | None = None,
    user_id: UUID | None = None,
) -> tuple[int, dict[str, int]]:
    """Evaluate BANT (Budget, Authority, Need, Timeline) score via DecisionService (AI-38.5).

    When DECISION_ENABLED and DECISION_VOICE_ENABLED are on, evaluates the
    transcript using the 'bant_scoring' SCORE question set (task='voice').
    Each pillar contributes 0 to 25 points from graduated 0-3 levels.
    Falls back to keyword heuristics on error or when disabled.
    """
    if not transcript or not transcript.strip():
        return 0, {"budget": 0, "authority": 0, "need": 0, "timeline": 0}

    try:
        from app.config import decision as decision_config

        if (
            decision_config.decision_enabled()
            and decision_config.decision_task_enabled("voice")
        ):
            from app.services.decision.questions import get_question_registry
            from app.services.decision.service import get_decision_service

            registry = get_question_registry()
            qs = registry.get_set("bant_scoring")
            decision_service = get_decision_service()

            result = await decision_service.decide(
                state={"transcript": transcript[:4000]},
                questions=dict(qs.questions),
                task="voice",
                question_set=f"{qs.name}@{qs.version}",
                required_state_keys=qs.required_state_keys,
                session=session,
                workspace_id=workspace_id,
                user_id=user_id,
            )

            breakdown: dict[str, int] = {}
            for dim in ("budget", "authority", "need", "timeline"):
                ans = result.answers.get(dim)
                if ans is not None and isinstance(ans.value, (int, float)):
                    # Scale score from [0.0, 3.0] to [0, 25] points
                    pts = round(float(ans.value) / 3.0 * 25.0)
                    breakdown[dim] = max(0, min(25, pts))
                else:
                    breakdown[dim] = 0

            total = sum(breakdown.values())
            return total, breakdown
    except Exception:
        logger.warning(
            "[VoiceBilling] BANT Jev scoring failed, falling back to keyword heuristic",
            exc_info=True,
        )

    return _evaluate_bant_score_keywords(transcript, call_metadata)


def evaluate_bant_score(
    transcript: str,
    call_metadata: dict[str, Any] | None = None,
) -> tuple[int, dict[str, int]]:
    """Evaluate BANT (Budget, Authority, Need, Timeline) score from 0 to 100.

    When DECISION_ENABLED and DECISION_VOICE_ENABLED are active, runs graduated
    scoring via DecisionService (falling back to keyword heuristics).

    Returns:
        tuple[total_score, breakdown_dict]
    """
    if not transcript or not transcript.strip():
        return 0, {"budget": 0, "authority": 0, "need": 0, "timeline": 0}

    try:
        from app.config import decision as decision_config

        if (
            decision_config.decision_enabled()
            and decision_config.decision_task_enabled("voice")
        ):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None:
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(
                        asyncio.run,
                        aevaluate_bant_score(transcript, call_metadata),
                    ).result(timeout=2.0)
            else:
                return asyncio.run(aevaluate_bant_score(transcript, call_metadata))
    except Exception:
        logger.warning(
            "[VoiceBilling] BANT synchronous evaluation failed, falling back to keyword heuristic",
            exc_info=True,
        )

    return _evaluate_bant_score_keywords(transcript, call_metadata)


async def sync_call_to_lead_activity_log(
    session: AsyncSession,
    *,
    workspace_id: int,
    lead_id: UUID,
    actor_user_id: UUID | None,
    call_duration_seconds: float,
    billed_seconds: int,
    cost_micros: int,
    bant_score: int,
    bant_breakdown: dict[str, int],
    transcript_summary: str = "",
    hangup_cause: str = "completed",
    room_name: str | None = None,
) -> LeadActivityLog:
    """Sync completed Voice AI SDR call results into LeadActivityLog timeline.

    Zero-Reinvention: Uses existing LeadActivityLog table with activity_type="voice_call".
    """
    details = {
        "call_duration_seconds": round(call_duration_seconds, 2),
        "billed_seconds": billed_seconds,
        "cost_micros": cost_micros,
        "cost_vnd": round(cost_micros / 1000.0, 2),
        "hangup_cause": hangup_cause,
        "bant_score": bant_score,
        "bant_breakdown": bant_breakdown,
        "transcript_summary": transcript_summary,
        "room_name": room_name,
    }

    title = f"Voice AI Call ({round(call_duration_seconds)}s) — BANT {bant_score}/100"

    log_entry = LeadActivityLog(
        workspace_id=workspace_id,
        lead_id=lead_id,
        actor_user_id=actor_user_id,
        activity_type="voice_call",
        title=title,
        details=details,
    )
    session.add(log_entry)
    await session.flush()

    logger.info(
        "[CRM] Logged voice_call activity ws=%s lead=%s bant=%s cost=%s",
        workspace_id,
        lead_id,
        bant_score,
        cost_micros,
    )
    return log_entry
