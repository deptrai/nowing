#!/usr/bin/env python3
"""Story 39.5 live verification: real VN messages -> real Jev intent labels.

Proves the intent-classification layer end to end against the real
TypeSafe System One backend (no mocks, no DB) on the
``intent_classify@1.0.0`` Choice set:

  battery   ~10 Vietnamese messages — one or two per intent category,
            drawn from the eval harness cases (scripts/jev_eval/
            cases.py INTENT_CLASSIFY, 95% baseline on 20 cases) —
            through classify_intent. Prints expected vs actual label,
            confidence, model and backend.
  edge      empty / whitespace messages — must return None with zero
            backend calls (skipped before any paid call).

Usage:
    TYPESAFE_API_KEY=... DECISION_ENABLED=true DECISION_INTENT_ENABLED=true \
    DECISION_BACKEND=jev uv run python scripts/verify_intent_classification_39_5.py

Reads decision config from the environment; exits early if the key or
the flags are missing (fail-open is the production default, so the
check is explicit here to avoid a silent no-op run).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("verify_39_5")

from app.services.intent_classification import classify_intent  # noqa: E402


def _check_env() -> None:
    if not os.environ.get("TYPESAFE_API_KEY"):
        sys.exit("TYPESAFE_API_KEY is not set — real Jev calls impossible")
    for var in ("DECISION_ENABLED", "DECISION_INTENT_ENABLED"):
        # Match app.config.decision._env_flag: only "true" enables —
        # "1"/"yes" would pass a looser guard then fail-open every call.
        if os.environ.get(var, "").strip().lower() != "true":
            sys.exit(f"{var} is not enabled — run would silently fail-open")
    backend = os.environ.get("DECISION_BACKEND", "jev").strip().lower()
    if backend != "jev":
        sys.exit(
            f"DECISION_BACKEND={backend!r} — labels would come from {backend}, not Jev"
        )


# ~10 crafted VN messages covering all 8 intent labels — the first per
# category is the eval-harness case (scripts/jev_eval/cases.py).
BATTERY: list[tuple[str, str]] = [
    # (expected_label, user_message)
    ("search", "Tìm cho tôi quán phở ngon ở Hà Nội"),
    ("search", "Giá Bitcoin hôm nay bao nhiêu?"),
    ("action", "Tạo báo cáo doanh thu tháng này"),
    ("action", "Đặt lịch họp vào 3 giờ chiều mai"),
    ("question", "Tại sao trời mưa?"),
    ("comparison", "iPhone 15 hay Samsung S24 tốt hơn?"),
    ("recommendation", "Gợi ý cho tôi món ăn tối nay"),
    ("chitchat", "Chào buổi sáng, khỏe không?"),
    ("complaint", "App của bạn chạy chậm quá, không tải được dữ liệu"),
    ("feedback", "Tính năng này rất hay, nhưng tôi muốn thêm dark mode"),
]


async def run_battery() -> None:
    print("[battery] crafted VN cases through classify_intent (real Jev)")
    hits = 0
    for expected, message in BATTERY:
        payload = await classify_intent(message)
        if payload is None:
            print(
                f"  {message[:50]!r:<54} expected={expected:<14} "
                f"got=None (below gate or fail-open)"
            )
            continue
        got = payload["label"]
        mark = "OK " if got == expected else "MISS"
        hits += got == expected
        print(
            f"  {mark} {message[:48]!r:<52} expected={expected:<14} "
            f"got={got:<14} conf={payload['confidence']:.2f} "
            f"model={payload['model']} backend={payload['backend']}"
        )
    print(f"[battery] {hits}/{len(BATTERY)} matched expected label")


async def run_edge() -> None:
    print("[edge] empty/whitespace messages (no backend call expected)")
    for message in ("", "   ", " \n\t "):
        payload = await classify_intent(message)
        print(f"  {message!r:<10} -> {payload}")
        assert payload is None, f"expected None for {message!r}, got {payload}"


async def main() -> None:
    _check_env()
    await run_battery()
    await run_edge()


if __name__ == "__main__":
    asyncio.run(main())
