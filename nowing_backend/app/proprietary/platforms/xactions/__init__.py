"""XActions social ingress integration package (AD-SOC-1 to AD-SOC-7)."""

from .adapter import XActionsSocialAdapter
from .models import SocialMonitoredTargetData, SocialPostData
from .phone_extractor import (
    SocialEntityExtractor,
    classify_social_intent,
    extract_phone_numbers,
    normalize_vietnamese_text,
)

__all__ = [
    "SocialEntityExtractor",
    "SocialMonitoredTargetData",
    "SocialPostData",
    "XActionsSocialAdapter",
    "classify_social_intent",
    "extract_phone_numbers",
    "normalize_vietnamese_text",
]
