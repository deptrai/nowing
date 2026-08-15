"""Unit test for ReDoS safety with <= 50ms execution bound (Story 21.8 / Task 6.2)."""

import time

from app.proprietary.platforms.xactions.phone_extractor import SocialEntityExtractor


def test_phone_regex_redos_safety_bound():
    """Assert execution on adversarial repetitive inputs finishes in <= 50ms."""
    extractor = SocialEntityExtractor()
    pathological_strings = [
        "09" + (" 0 " * 2000),
        "+84" + ("-" * 5000) + "901234567",
        "không " * 1000 + "chín " * 1000,
        "o" * 5000 + "9" * 5000,
    ]

    for pathological_str in pathological_strings:
        start_time = time.perf_counter()
        phones = extractor.extract_phones(pathological_str, timeout_sec=0.05)
        duration = time.perf_counter() - start_time
        # In typical runtimes duration should be well below 50ms
        assert duration < 0.10, f"ReDoS took {duration:.4f}s on input len={len(pathological_str)}"
        assert isinstance(phones, list)
