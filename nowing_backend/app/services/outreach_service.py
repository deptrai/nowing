"""B2B Outreach Draft Engine & Buying Signal Correlation (Story 21.9 / AC-3)."""

from __future__ import annotations

import logging
from enum import StrEnum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class OutreachSignalType(StrEnum):
    """Buying signal types that trigger personalized sales outreach."""

    HIRING_SPIKE = "hiring_spike"
    TENDER_WIN = "tender_win"
    FUNDING_ROUND = "funding_round"
    EXPANSION = "expansion"
    GENERAL_PROSPECTING = "general_prospecting"


class OutreachDraftRequest(BaseModel):
    """Payload for generating personalized B2B outreach draft."""

    executive_name: str = Field(..., description="Recipient full name")
    executive_title: str | None = Field(default=None, description="Recipient title / role")
    company_name: str = Field(..., description="Recipient company name")
    signal_type: OutreachSignalType = Field(
        default=OutreachSignalType.GENERAL_PROSPECTING,
        description="Trigger signal type",
    )
    signal_details: str | None = Field(
        default=None,
        description="Context of the signal (e.g., 'Tuyển 25 kỹ sư', 'Trúng thầu 50 tỷ')",
    )
    offering_name: str = Field(..., description="Product / Service name being offered")
    offering_value_prop: str = Field(
        ...,
        description="Value proposition or specific benefit to the recipient",
    )
    sender_name: str = Field(..., description="Sender full name")
    sender_title: str | None = Field(default=None, description="Sender job title")
    sender_company: str | None = Field(default="Nowing", description="Sender company name")
    tone: str = Field(default="consultative_professional", description="Tone of the email")
    language: str = Field(default="vi", description="Language: 'vi' or 'en'")


class OutreachDraftResponse(BaseModel):
    """Generated outreach email with subject, text, HTML, and CTA."""

    subject_line: str
    body_text: str
    body_html: str
    call_to_action: str
    personalization_hooks: list[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.85)


class B2BOutreachService:
    """Service to draft contextual B2B sales emails grounded in buying signals."""

    def generate_outreach_draft(self, request: OutreachDraftRequest) -> OutreachDraftResponse:
        """Generate high-converting contextual outreach draft."""
        name = request.executive_name.strip()
        title = request.executive_title or "Lãnh đạo"
        company = request.company_name.strip()
        signal_type = request.signal_type
        signal_details = request.signal_details or ""
        offering = request.offering_name.strip()
        val_prop = request.offering_value_prop.strip()
        sender = request.sender_name.strip()
        sender_title = request.sender_title or "Đại diện giải pháp"
        sender_company = request.sender_company or "Nowing"

        hooks: list[str] = []

        if signal_type == OutreachSignalType.HIRING_SPIKE:
            subject = f"Chiến lược tăng tốc quy mô nhân sự tại {company} cùng {offering}"
            hook = f"Tôi nhận thấy {company} đang có bước phát triển vượt bậc và mở rộng tuyển dụng mạnh mẽ ({signal_details})."
            hooks.append(f"Hiring Growth Signal: {signal_details}")
            body_intro = (
                f"Kính gửi Anh/Chị {name} ({title} tại {company}),\n\n"
                f"{hook}\n\n"
                f"Khi mở rộng quy mô đội ngũ với tốc độ nhanh, thách thức lớn nhất thường là tối ưu chi phí vận hành và rút ngắn thời gian thích ứng của nhân sự mới.\n\n"
                f"Giải pháp {offering} giúp {company} {val_prop.lower()}."
            )
        elif signal_type == OutreachSignalType.TENDER_WIN:
            subject = f"Chúc mừng {company} trúng gói thầu mới & Giải pháp đồng hành cùng {offering}"
            hook = f"Chúc mừng {company} và Anh/Chị {name} vừa đạt được bước tiến lớn với gói thầu ({signal_details})."
            hooks.append(f"Tender Win Signal: {signal_details}")
            body_intro = (
                f"Kính gửi Anh/Chị {name} ({title} tại {company}),\n\n"
                f"{hook}\n\n"
                f"Để đảm bảo tiến độ triển khai và tối ưu chi phí cung ứng cho dự án lớn này, chúng tôi sẵn sàng đồng hành hỗ trợ {company}.\n\n"
                f"Với {offering}, chúng tôi cam kết giúp {company} {val_prop.lower()}."
            )
        elif signal_type == OutreachSignalType.FUNDING_ROUND:
            subject = f"Chúc mừng cột mốc gọi vốn của {company} & Đề xuất hợp tác từ {sender_company}"
            hook = f"Xin chúc mừng {company} với vòng gọi vốn thành công gần đây ({signal_details})."
            hooks.append(f"Funding Round Signal: {signal_details}")
            body_intro = (
                f"Kính gửi Anh/Chị {name} ({title} tại {company}),\n\n"
                f"{hook}\n\n"
                f"Trong giai đoạn tăng tốc này, giải pháp {offering} sẽ là đòn bẩy giúp {company} {val_prop.lower()}."
            )
        else:
            subject = f"Đề xuất hợp tác tối ưu hiệu quả doanh nghiệp cho {company}"
            hook = f"Theo dõi hành trình phát triển ấn tượng của {company} trong ngành."
            hooks.append(f"Executive Outreach: {title} @ {company}")
            body_intro = (
                f"Kính gửi Anh/Chị {name} ({title} tại {company}),\n\n"
                f"{hook}\n\n"
                f"Chúng tôi nhận thấy cơ hội hợp tác chiến lược giữa hai bên, đặc biệt trong việc giúp {company} {val_prop.lower()} thông qua {offering}."
            )

        cta = f"Anh/Chị {name} có sẵn sàng dành 15 phút đầu tuần tới để chúng ta cùng trao đổi ngắn qua Google Meet/Zoom không?"

        body_text = (
            f"{body_intro}\n\n"
            f"{cta}\n\n"
            f"Trân trọng,\n"
            f"{sender}\n"
            f"{sender_title} | {sender_company}"
        )

        body_html = (
            f"<p>Kính gửi Anh/Chị <strong>{name}</strong> ({title} tại <strong>{company}</strong>),</p>"
            f"<p>{hook}</p>"
            f"<p>Giải pháp <strong>{offering}</strong> được thiết kế để giúp {company} {val_prop.lower()}.</p>"
            f"<p><strong>{cta}</strong></p>"
            f"<p>Trân trọng,<br/>"
            f"<strong>{sender}</strong><br/>"
            f"{sender_title} | {sender_company}</p>"
        )

        return OutreachDraftResponse(
            subject_line=subject,
            body_text=body_text,
            body_html=body_html,
            call_to_action=cta,
            personalization_hooks=hooks,
            confidence_score=0.88 if signal_details else 0.75,
        )
