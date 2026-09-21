"""Intent classification question set — Choice over intent categories.

Ported from ``scripts/jev_eval/cases.py`` (INTENT_CLASSIFY). Eval
baseline: 95% on 20 Vietnamese cases. Caller puts ``user_message`` in
``state``.
"""

from __future__ import annotations

from app.services.decision.types import ChoiceQuestion

VERSION = "1.0.0"

INTENT_OPTIONS: dict[str, str] = {
    "search": "Tìm kiếm thông tin, tra cứu",
    "action": "Thực hiện hành động (tạo, đặt, gửi)",
    "question": "Câu hỏi kiến thức, giải thích",
    "comparison": "So sánh hai hay nhiều thứ",
    "recommendation": "Xin gợi ý, tư vấn",
    "chitchat": "Trò chuyện, chào hỏi",
    "complaint": "Phàn nàn, khiếu nại",
    "feedback": "Góp ý, đánh giá",
}

QUESTIONS: dict[str, ChoiceQuestion] = {
    "intent": ChoiceQuestion(
        instructions=(
            "Classify the Vietnamese user's primary intent. Pick the single "
            "best category."
        ),
        criteria=INTENT_OPTIONS,
    ),
}
