"""Voice Profile Learning Engine (Story 21.12 / AC 1 / AD-SOC-1 / AD-11)."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.schemas.voice_profile import FormattingQuirks, VoiceProfile

logger = logging.getLogger(__name__)


class VoiceProfileLearner:
    """Extracts tone, cadence, vocabulary, hook patterns, and formatting style from user writing samples."""

    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm_client = llm_client

    async def extract_voice_profile(
        self,
        sample_text: str,
        profile_name: str,
        platform: str = "facebook",
    ) -> VoiceProfile:
        """Analyze sample text and extract a structured VoiceProfile."""
        words = [w for w in sample_text.strip().split() if w]
        if len(words) < 100:
            raise ValueError(
                "Sample text must contain at least 100 words for accurate voice profiling."
            )

        # Deterministic text analytics
        sentences = [s.strip() for s in re.split(r"[.!?\n]+", sample_text) if s.strip()]
        avg_sentence_len = (
            round(sum(len(s.split()) for s in sentences) / max(len(sentences), 1), 1)
            if sentences
            else 12.0
        )

        # Tone analysis heuristics
        lower_sample = sample_text.lower()
        tones = []
        if any(
            w in lower_sample
            for w in ["hầu hết", "sai lầm", "thực tế", "đừng", "dừng", "sự thật"]
        ):
            tones.append("authoritative")
            tones.append("contrarian")
        if any(
            w in lower_sample
            for w in ["tôi", "mình", "kinh nghiệm", "chia sẻ", "bài học"]
        ):
            tones.append("pragmatic")
            tones.append("direct")
        if not tones:
            tones = ["authoritative", "direct"]
        tone_str = ", ".join(dict.fromkeys(tones))

        # Hook preference heuristics
        if any(
            w in lower_sample
            for w in ["hầu hết", "sai lầm", "đừng chạy theo", "đốt tiền"]
        ):
            hook_pref = "contrarian hook with specific numbers"
        elif any(
            w in lower_sample for w in ["quy trình", "bước", "bí quyết", "checklist"]
        ):
            hook_pref = "actionable framework with step-by-step numbers"
        elif "%" in sample_text or any(char.isdigit() for char in sample_text):
            hook_pref = "data reveal with percentage metrics"
        else:
            hook_pref = "story shift before-and-after"

        # Vocabulary extraction: extract salient domain words
        vocab_candidates = [
            "dòng tiền",
            "phân khúc cao cấp",
            "định vị",
            "thực chiến",
            "tệp khách",
            "bất động sản",
            "chuyên sâu",
            "định giá",
            "roi",
            "pipeline",
            "growth",
            "quy trình",
            "đòn bẩy",
        ]
        extracted_vocab = [v for v in vocab_candidates if v in lower_sample]
        if not extracted_vocab:
            # Fallback to frequent words (> 4 chars)
            clean_words = [
                re.sub(r"[^\w\s]", "", w.lower()) for w in words if len(w) > 4
            ]
            freq: dict[str, int] = {}
            for w in clean_words:
                freq[w] = freq.get(w, 0) + 1
            extracted_vocab = sorted(freq, key=freq.get, reverse=True)[:5]

        # Formatting quirks
        emoji_count = len(re.findall(r"[\U00010000-\U0010ffff]", sample_text))
        emoji_density = (
            "none"
            if emoji_count == 0
            else "low"
            if emoji_count < 3
            else "medium"
            if emoji_count < 7
            else "high"
        )

        has_numbered = bool(re.search(r"^\s*\d+[\.\)]\s+", sample_text, re.MULTILINE))
        has_bullets = bool(re.search(r"^\s*[-*•]\s+", sample_text, re.MULTILINE))
        bullet_style = (
            "numbered_list" if has_numbered else "bullet" if has_bullets else "none"
        )

        line_breaks = sample_text.count("\n")
        line_break_freq = (
            "high"
            if line_breaks > len(words) // 20
            else "medium"
            if line_breaks > 3
            else "low"
        )

        quirks = FormattingQuirks(
            emoji_density=emoji_density,
            bullet_style=bullet_style,
            line_break_frequency=line_break_freq,
        )

        return VoiceProfile(
            profile_name=profile_name,
            tone=tone_str,
            average_sentence_length=avg_sentence_len,
            paragraph_cadence="short paragraphs, 1-2 sentences per line, high whitespace",
            hook_preference=hook_pref,
            vocabulary=extracted_vocab,
            formatting_quirks=quirks,
            is_active=True,
        )
