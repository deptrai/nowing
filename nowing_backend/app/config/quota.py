"""Config domain: quota."""

from __future__ import annotations

import os

# Anonymous / no-login mode settings
NOLOGIN_MODE_ENABLED = os.getenv("NOLOGIN_MODE_ENABLED", "FALSE").upper() == "TRUE"
ANON_TOKEN_LIMIT = int(os.getenv("ANON_TOKEN_LIMIT", "500000"))
ANON_TOKEN_WARNING_THRESHOLD = int(
    os.getenv("ANON_TOKEN_WARNING_THRESHOLD", "400000")
)
ANON_TOKEN_QUOTA_TTL_DAYS = int(os.getenv("ANON_TOKEN_QUOTA_TTL_DAYS", "30"))
ANON_MAX_UPLOAD_SIZE_MB = int(os.getenv("ANON_MAX_UPLOAD_SIZE_MB", "5"))

# Default quota reserve tokens when not specified per-model
QUOTA_MAX_RESERVE_PER_CALL = int(os.getenv("QUOTA_MAX_RESERVE_PER_CALL", "8000"))

# Per-image reservation (in micro-USD) used by ``billable_call`` for the
# ``POST /image-generations`` endpoint when the global config does not
# override it. $0.05 covers realistic worst-cases for current OpenAI /
# OpenRouter image-gen pricing. Bypassed entirely for free configs.
QUOTA_DEFAULT_IMAGE_RESERVE_MICROS = int(
    os.getenv("QUOTA_DEFAULT_IMAGE_RESERVE_MICROS", "50000")
)

# Per-podcast reservation (in micro-USD). One chat model call generating
# a transcript, typically 5k-20k completion tokens. $0.20 covers a long
# premium-model run. Tune via env.
QUOTA_DEFAULT_PODCAST_RESERVE_MICROS = int(
    os.getenv("QUOTA_DEFAULT_PODCAST_RESERVE_MICROS", "200000")
)

# Per-video-presentation reservation (in micro-USD). Fan-out of N
# slide-scene generations (up to ``VIDEO_PRESENTATION_MAX_SLIDES=30``)
# plus refine retries; can produce many premium completions. $1.00
# covers worst-case. Tune via env.
#
# NOTE: this equals the existing ``QUOTA_MAX_RESERVE_MICROS`` default of
# 1_000_000. The override path in ``billable_call`` bypasses the
# per-call clamp in ``estimate_call_reserve_micros``, so this is the
# *actual* hold — raising it via env is fine but means a single video
# task can lock $1+ of credit.
QUOTA_DEFAULT_VIDEO_PRESENTATION_RESERVE_MICROS = int(
    os.getenv("QUOTA_DEFAULT_VIDEO_PRESENTATION_RESERVE_MICROS", "1000000")
)

# Abuse prevention: concurrent stream cap and CAPTCHA
ANON_MAX_CONCURRENT_STREAMS = int(os.getenv("ANON_MAX_CONCURRENT_STREAMS", "2"))
ANON_CAPTCHA_REQUEST_THRESHOLD = int(
    os.getenv("ANON_CAPTCHA_REQUEST_THRESHOLD", "5")
)



__all__ = ['ANON_CAPTCHA_REQUEST_THRESHOLD', 'ANON_MAX_CONCURRENT_STREAMS', 'ANON_MAX_UPLOAD_SIZE_MB', 'ANON_TOKEN_LIMIT', 'ANON_TOKEN_QUOTA_TTL_DAYS', 'ANON_TOKEN_WARNING_THRESHOLD', 'NOLOGIN_MODE_ENABLED', 'QUOTA_DEFAULT_IMAGE_RESERVE_MICROS', 'QUOTA_DEFAULT_PODCAST_RESERVE_MICROS', 'QUOTA_DEFAULT_VIDEO_PRESENTATION_RESERVE_MICROS', 'QUOTA_MAX_RESERVE_PER_CALL']
