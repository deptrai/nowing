"""Suggested Action Pills Generator (Story 21.11 / AC: 1, 4).

Generates contextual 1-click execution chips (SuggestedAction) appended to the
final SSE stream of a completed chat turn. Supports dynamic selection count ($N$)
and credit projection ($1.5 \times N$).
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.new_chat import SuggestedAction

_PHONE_MASK_PATTERN = re.compile(
    r"(?<!\d)(?:\+?84|0)(?:3|5|7|8|9)(?:[\s.-]?\d){2,5}[\s.-]?(?:[xX*•]{2,6}|\.{3})(?:[\s.-]?\d{1,4})?",
    re.IGNORECASE,
)
_PHONE_KEYWORD_PATTERN = re.compile(
    r"\b(sđt|số điện thoại|phone|liên hệ|chủ nhà|môi giới|ẩn số|ẩn sđt|decode|giải mã)\b",
    re.IGNORECASE,
)
_LEAD_OR_COMPANY_PATTERN = re.compile(
    r"\b(công ty|doanh nghiệp|ứng viên|tuyển dụng|lead|khách hàng|bất động sản|nhà đất|bds|đấu thầu|shopee|gian hàng|sản phẩm)\b",
    re.IGNORECASE,
)
_TABLE_OR_LIST_PATTERN = re.compile(
    r"(\|\s*[-:]+\s*\||1\.\s+\*\*|2\.\s+\*\*|STT|Danh sách|Bảng kết quả)",
    re.IGNORECASE,
)


def _detect_masked_phone_count(text: str) -> int:
    """Extract count of masked phone patterns in text."""
    if not isinstance(text, str) or not text.strip():
        return 0
    matches = _PHONE_MASK_PATTERN.findall(text)
    return len(matches)


def generate_suggested_actions(
    user_query: str = "",
    assistant_text: str = "",
    tool_names: list[str] | None = None,
    selection_count: int | None = None,
    payload_context: dict[str, Any] | None = None,
) -> list[SuggestedAction]:
    """Generate up to 3 contextual SuggestedAction pills for a completed chat turn.

    Args:
        user_query: The incoming user prompt for this turn.
        assistant_text: Final generated text response from the assistant.
        tool_names: Names of tools called during this turn (if any).
        selection_count: Number of selected items (e.g. from lead intelligence table).
        payload_context: Optional additional metadata from the UI/request.

    Returns:
        List of at most 3 SuggestedAction models.
    """
    tools = set(tool_names or [])
    combined_text = f"{user_query}\n{assistant_text}"
    actions: list[SuggestedAction] = []

    # 1. Phone Decoding Action (P0 for Lead/Scraper intelligence)
    has_scraper_tools = bool(
        tools.intersection(
            {
                "batdongsan_search",
                "batdongsan_details",
                "muaban_bds_search",
                "muaban_bds_details",
                "telegram_search",
                "telegram_channel_preview",
                "shopee_search",
                "masothue_company_search",
                "linkedin_jobs_search",
                "search_leads",
                "decode_phone_number",
            }
        )
    )
    has_phone_keywords = bool(_PHONE_KEYWORD_PATTERN.search(combined_text))
    masked_count = _detect_masked_phone_count(assistant_text)

    if has_scraper_tools or has_phone_keywords or masked_count > 0 or (selection_count and selection_count > 0):
        # Calculate dynamic count N
        if selection_count is not None and selection_count > 0:
            n_count = selection_count
        elif masked_count > 0:
            n_count = masked_count
        elif has_scraper_tools:
            n_count = 5  # default estimate when scraper yields multiple leads
        else:
            n_count = 1

        cost = round(1.5 * n_count, 2)
        if n_count > 1 or (selection_count is not None and selection_count > 0):
            label = f"📱 Giải mã {n_count} SĐT ({cost:g} credits)"
            prompt = f"Giải mã {n_count} số điện thoại của các liên hệ trên để lấy thông tin liên lạc đầy đủ."
        else:
            label = "📱 Giải mã SĐT (1.5 credits/số)"
            prompt = "Giải mã số điện thoại của các liên hệ trong kết quả trên để lấy thông tin liên lạc đầy đủ."

        actions.append(
            SuggestedAction(
                id="decode_phones",
                label=label,
                icon="phone",
                action_type="decode_phones",
                prompt_template=prompt,
                cost_credits=cost,
                payload={"selection_count": n_count, "cost_per_unit": 1.5, "total_cost": cost},
            )
        )

    # 2. Zalo Outreach / Sales Script Draft
    has_lead_keywords = bool(_LEAD_OR_COMPANY_PATTERN.search(combined_text))
    if has_scraper_tools or has_lead_keywords:
        actions.append(
            SuggestedAction(
                id="zalo_draft",
                label="💬 Tạo tin nhắn Zalo mẫu",
                icon="message-square",
                action_type="zalo_draft",
                prompt_template="Soạn kịch bản tin nhắn Zalo chuyên nghiệp để tiếp cận các liên hệ/ứng viên trong danh sách trên.",
                cost_credits=None,
                payload={"platform": "zalo"},
            )
        )

    # 3. Find Similar Leads / Candidates / Properties
    actions.append(
        SuggestedAction(
            id="find_similar",
            label="🎯 Tìm lead tương tự",
            icon="search",
            action_type="find_similar",
            prompt_template="Tìm kiếm thêm các khách hàng tiềm năng/bất động sản tương tự trong khu vực/ngành nghề này.",
            cost_credits=None,
            payload={},
        )
    )

    # 4. Export CSV / Table Data
    has_table = bool(_TABLE_OR_LIST_PATTERN.search(assistant_text)) or has_scraper_tools
    if has_table:
        actions.append(
            SuggestedAction(
                id="export_csv",
                label="📊 Xuất bảng CSV",
                icon="download",
                action_type="export_csv",
                prompt_template="Xuất toàn bộ danh sách kết quả ở trên thành file CSV.",
                cost_credits=None,
                payload={"format": "csv"},
            )
        )

    # 5. Deep Research / Comprehensive Strategy (Fallback)
    actions.append(
        SuggestedAction(
            id="deep_research",
            label="🔬 Nghiên cứu chuyên sâu",
            icon="sparkles",
            action_type="deep_research",
            prompt_template="Phân tích và nghiên cứu chuyên sâu hơn về các cơ hội kinh doanh và đối thủ trong danh sách này.",
            cost_credits=None,
            payload={"mode": "quality"},
        )
    )

    # De-duplicate by id preserving order and cap strictly at maximum 3 pills
    seen_ids: set[str] = set()
    unique_actions: list[SuggestedAction] = []
    for action in actions:
        if action.id not in seen_ids:
            seen_ids.add(action.id)
            unique_actions.append(action)
        if len(unique_actions) == 3:
            break

    return unique_actions
