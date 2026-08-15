"""Viral Post Rewrite Engine & Multi-Platform Constraints (Story 21.12 / AC 4)."""

from __future__ import annotations

import logging
from typing import Literal

from app.schemas.voice_profile import DraftVariation, VoiceProfile

logger = logging.getLogger(__name__)


class ViralDraftGenerator:
    """Generates voice-matched post variations applying platform constraints and hook taxonomies."""

    async def generate_drafts(
        self,
        topic: str,
        hook_taxonomy: str,
        voice_profile: VoiceProfile,
        target_platform: Literal[
            "twitter", "facebook", "linkedin", "threads"
        ] = "facebook",
        n_variations: int = 3,
    ) -> list[DraftVariation]:
        """Generate N distinct draft variations (A: contrarian, B: framework, C: case_study)."""
        variations: list[DraftVariation] = []
        letters: list[Literal["A", "B", "C"]] = ["A", "B", "C"]
        angles: list[Literal["contrarian", "framework", "case_study"]] = [
            "contrarian",
            "framework",
            "case_study",
        ]

        bullet_char = (
            "•" if voice_profile.formatting_quirks.bullet_style == "bullet" else "1."
        )

        vocab_tokens = (
            ", ".join(voice_profile.vocabulary[:3])
            if voice_profile.vocabulary
            else "tối ưu, tăng trưởng, thực chiến"
        )

        for i in range(min(n_variations, 3)):
            letter = letters[i]
            angle = angles[i]

            if angle == "contrarian":
                hook_line = f"Hầu hết mọi người đang hiểu sai về {topic}."
                re_hook = (
                    f"Thực tế, việc cố gắng áp dụng các phương pháp cũ chỉ khiến bạn lãng phí thời gian và ngân sách. "
                    f"Để tạo đột phá về {vocab_tokens}, bạn cần thay đổi tư duy ngay hôm nay:"
                )
                body_lines = [
                    f"{bullet_char} Nhận diện chính xác điểm nghẽn thực sự thay vì chữa triệu chứng.",
                    f"{bullet_char} Ứng dụng mô hình đòn bẩy để nhân rộng hiệu suất.",
                    f"{bullet_char} Đo lường kết quả dựa trên chỉ số chuyển đổi thực tế.",
                ]
                cta = "Bình luận 'TƯ DUY' để nhận tài liệu phân tích chi tiết."
            elif angle == "framework":
                hook_line = f"Quy trình 3 bước làm chủ {topic} cho người bận rộn:"
                re_hook = "Được đúc kết từ kinh nghiệm thực chiến, đây là khung giải pháp giúp bạn tối ưu hóa kết quả nhanh chóng:"
                body_lines = [
                    f"{bullet_char} Bước 1: Chuẩn hoá dữ liệu đầu vào và thiết lập mục tiêu.",
                    f"{bullet_char} Bước 2: Tối ưu quy trình vận hành và loại bỏ lãng phí.",
                    f"{bullet_char} Bước 3: Nhân bản quy trình với hệ thống tự động hoá.",
                ]
                cta = "Thả tim và lưu bài viết để áp dụng ngay hôm nay."
            else:  # case_study
                hook_line = (
                    f"Cách chúng tôi tăng trưởng đột phá với {topic} trong 6 tháng qua:"
                )
                re_hook = "Không cần ngân sách khổng lồ, chỉ cần tập trung đúng đòn bẩy chiến lược:"
                body_lines = [
                    f"{bullet_char} Bài học 1: Bắt đầu từ thị trường ngách có nhu cầu bức thiết.",
                    f"{bullet_char} Bài học 2: Kiểm chứng tính khả thi bằng phiên bản tinh gọn.",
                    f"{bullet_char} Bài học 3: Duy trì kỷ luật thực thi mỗi ngày.",
                ]
                cta = (
                    "Bạn ấn tượng nhất với bài học nào? Chia sẻ góc nhìn bên dưới nhé."
                )

            # Assemble draft content based on platform
            if target_platform == "twitter":
                full_raw = (
                    f"{hook_line}\n\n{re_hook}\n\n"
                    + "\n".join(body_lines)
                    + f"\n\n{cta}"
                )
                if len(full_raw) <= 280:
                    variations.append(
                        DraftVariation(
                            variation_letter=letter,
                            content=full_raw,
                            angle=angle,
                            estimated_reading_time_sec=30,
                            is_thread=False,
                            thread_tweets=[],
                        )
                    )
                else:
                    # Break into tweet thread chunks <= 280 chars
                    t1_text = f"{hook_line}\n\n{re_hook}"
                    tweet_1 = f"1/3 {t1_text[:270]}"
                    tweet_2 = f"2/3 {' '.join(body_lines)[:270]}"
                    tweet_3 = f"3/3 {cta[:270]}"
                    variations.append(
                        DraftVariation(
                            variation_letter=letter,
                            content=f"{tweet_1}\n\n{tweet_2}\n\n{tweet_3}",
                            angle=angle,
                            estimated_reading_time_sec=45,
                            is_thread=True,
                            thread_tweets=[tweet_1, tweet_2, tweet_3],
                        )
                    )
            elif target_platform == "linkedin":
                full_content = (
                    f"{hook_line}\n\n"
                    f"{re_hook}\n\n"
                    + "\n".join(body_lines)
                    + f"\n\n---\n{cta}\n\n#Nowing #{topic.replace(' ', '')}"
                )
                variations.append(
                    DraftVariation(
                        variation_letter=letter,
                        content=full_content,
                        angle=angle,
                        estimated_reading_time_sec=50,
                        is_thread=False,
                        thread_tweets=[],
                    )
                )
            elif target_platform == "threads":
                full_content = (
                    f"{hook_line}\n\n{re_hook}\n\n"
                    + "\n".join(body_lines)
                    + f"\n\n{cta}"
                )
                if len(full_content) > 500:
                    full_content = full_content[:495] + "..."
                variations.append(
                    DraftVariation(
                        variation_letter=letter,
                        content=full_content,
                        angle=angle,
                        estimated_reading_time_sec=35,
                        is_thread=False,
                        thread_tweets=[],
                    )
                )
            else:  # facebook (default)
                full_content = (
                    f"{hook_line}\n\n{re_hook}\n\n"
                    + "\n".join(body_lines)
                    + f"\n\n👉 {cta}"
                )
                variations.append(
                    DraftVariation(
                        variation_letter=letter,
                        content=full_content,
                        angle=angle,
                        estimated_reading_time_sec=60,
                        is_thread=False,
                        thread_tweets=[],
                    )
                )

        return variations
