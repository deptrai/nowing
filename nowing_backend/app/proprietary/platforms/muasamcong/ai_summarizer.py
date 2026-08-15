"""Procurement AI Summarizer & Countdown Intelligence Engine (Story 16.5 / AC-4 / AD-PROC-8)."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.proprietary.platforms.muasamcong.schemas import (
    CountdownInfo,
    ExecutiveSummary,
    QualificationCriteria,
)


class ProcurementAISummarizer:
    """Extracts 4 core qualification criteria and computes real-time deadline countdown."""

    def calculate_countdown(self, bid_closing_at: datetime | None) -> CountdownInfo:
        """Calculates time remaining until bid closing and urgency status (AD-PROC-8)."""
        if not bid_closing_at:
            return CountdownInfo(
                is_closed=False,
                is_urgent=False,
                hours_remaining=0.0,
                countdown_text="Chưa xác định thời điểm đóng thầu",
            )

        now = datetime.now(UTC)
        if not bid_closing_at.tzinfo:
            bid_closing_at = bid_closing_at.replace(tzinfo=UTC)

        diff = bid_closing_at - now
        total_seconds = diff.total_seconds()

        if total_seconds <= 0:
            return CountdownInfo(
                is_closed=True,
                is_urgent=False,
                hours_remaining=0.0,
                countdown_text="Đã đóng thầu",
            )

        hours_remaining = round(total_seconds / 3600.0, 1)
        days = int(diff.days)
        hours = int(diff.seconds // 3600)
        minutes = int((diff.seconds % 3600) // 60)

        # Trigger urgency precisely when total seconds < 48h (AD-PROC-8)
        is_urgent = total_seconds < (48.0 * 3600.0)

        if days > 0:
            countdown_text = f"Còn {days} ngày {hours} giờ"
        elif hours > 0:
            countdown_text = f"Còn {hours} giờ {minutes} phút"
        else:
            countdown_text = f"Còn {minutes} phút (Sắp đóng thầu!)"

        return CountdownInfo(
            is_closed=False,
            is_urgent=is_urgent,
            hours_remaining=hours_remaining,
            countdown_text=countdown_text,
        )

    def extract_qualification_from_text(self, text: str) -> QualificationCriteria:
        """Heuristic and regex extraction for 4 core HSMT qualification requirements."""
        if not text:
            return QualificationCriteria()

        annual_turnover = "Không có thông tin cụ thể"
        similar_contracts = "Không có thông tin cụ thể"
        key_personnel = "Không có thông tin cụ thể"
        bid_security = "Không có thông tin cụ thể"

        lines = text.split("\n")
        for line in lines:
            line_str = line.strip()
            if not line_str or len(line_str) < 5:
                continue

            # Limit criteria length to max 500 chars
            clean_str = line_str[:500]

            # 1. Doanh thu bình quân hàng năm
            if re.search(r"(doanh\s*thu\s*bình\s*quân|năng\s*lực\s*tài\s*chính|turnover)", clean_str, re.IGNORECASE):
                # Prefer lines that contain numbers or currency
                if any(c.isdigit() for c in clean_str) or annual_turnover == "Không có thông tin cụ thể":
                    annual_turnover = clean_str

            # 2. Hợp đồng tương tự
            elif re.search(r"(hợp\s*đồng\s*tương\s*tự|kinh\s*nghiệm\s*thực\s*hiện|similar\s*contract)", clean_str, re.IGNORECASE):
                if any(c.isdigit() for c in clean_str) or similar_contracts == "Không có thông tin cụ thể":
                    similar_contracts = clean_str

            # 3. Nhân sự chủ chốt
            elif re.search(r"(nhân\s*sự\s*chủ\s*chốt|chỉ\s*huy\s*trưởng|chủ\s*nhiệm|key\s*personnel)", clean_str, re.IGNORECASE):
                key_personnel = clean_str

            # 4. Bảo đảm dự thầu
            elif re.search(r"(bảo\s*đảm\s*dự\s*thầu|tiền\s*bảo\s*đảm|thư\s*bảo\s*lãnh|bid\s*security)", clean_str, re.IGNORECASE):
                bid_security = clean_str

        return QualificationCriteria(
            annual_turnover=annual_turnover,
            similar_contracts=similar_contracts,
            key_personnel=key_personnel,
            bid_security=bid_security,
        )

    async def summarize_hsmt(
        self,
        bid_no: str,
        raw_text: str | None = None,
        bid_closing_at: datetime | None = None,
        bid_turn_no: str = "00",
        procuring_entity: str | None = None,
    ) -> ExecutiveSummary:
        """Produces a structured Executive Summary with 4 core criteria and countdown."""
        countdown = self.calculate_countdown(bid_closing_at)
        qualification = self.extract_qualification_from_text(raw_text or "")

        notes = (
            f"Gói thầu {bid_no} ({countdown.countdown_text}). "
            f"Bên mời thầu: {procuring_entity or 'Chưa xác định'}."
        )

        return ExecutiveSummary(
            bid_no=bid_no,
            bid_turn_no=bid_turn_no,
            qualification=qualification,
            countdown=countdown,
            procuring_entity=procuring_entity,
            summary_notes=notes,
        )
