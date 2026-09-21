"""Subagent routing question set — Choice over the subagent roster.

Ported from ``scripts/jev_eval/cases.py`` (SUBAGENT_ROUTING). Eval
baseline: 100% on 20 Vietnamese cases. Instructions in English; the
caller puts the natural Vietnamese ``user_message`` in ``state`` (AD-J8).
"""

from __future__ import annotations

from app.services.decision.types import ChoiceQuestion

VERSION = "1.0.0"

SUBAGENT_OPTIONS: dict[str, str] = {
    "chainlens": "Deep multi-source research, web intelligence, cited answers",
    "batdongsan": "Real estate listings on batdongsan.com.vn",
    "chotot": "Classified listings on chotot.com",
    "google_maps": "Places, businesses, addresses on Google Maps",
    "google_search": "Quick web search for simple lookups",
    "vietstock": "Vietnamese stock market data",
    "youtube": "YouTube video search + transcripts",
    "reddit": "Reddit posts and discussions",
    "tiktok": "TikTok videos and trends",
    "knowledge_base": "User's saved documents and notes",
    "memory": "User profile, preferences, past conversations",
    "vn_jobs": "Vietnamese job listings (TopCV, VietnamWorks, ITViec)",
    "web_crawler": "Generic web page crawling for arbitrary URLs",
    "instagram": "Instagram profiles, posts, hashtags",
    "deliverables": "Generate reports, slides, spreadsheets",
    "none_needed": "Simple chat reply, no specialist needed",
}

QUESTIONS: dict[str, ChoiceQuestion] = {
    "subagent": ChoiceQuestion(
        instructions=(
            "Which specialist should handle this Vietnamese user request? "
            "Pick the most specific match. If no specialist applies (casual "
            "chat, creative writing, general knowledge), pick 'none_needed'."
        ),
        criteria=SUBAGENT_OPTIONS,
    ),
}
