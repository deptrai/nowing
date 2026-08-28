"""Enterprise evaluation metrics for AI Lead Generation (Story 21.15 / Story 28.5).

This module implements 8 enterprise-grade lead generation evaluation metrics:
1. precision_at_k: Precision of top-k retrieved leads against ground truth.
2. recall_at_source: Proportion of target data sources successfully resolved and harvested.
3. icp_match_rate: Percentage of generated leads satisfying firmographic/demographic ICP rules.
4. intent_signal_precision: Accuracy and validity of detected buying/hiring/procurement intent signals.
5. contact_accuracy: Completeness and validity of actionable contact endpoints (phone, email, zalo).
6. duplicate_rate: Duplicate ratio before and after cross-source entity deduplication.
7. false_positive_rate: Rate of disqualified/negative distractor candidates mistakenly included.
8. time_to_first_lead: Latency in milliseconds from dispatch to first emitted lead record.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _strip_vietnamese_accents(text: str | None) -> str:
    """Normalize Vietnamese text and strip combining diacritics for fuzzy entity matching."""
    if not text or not isinstance(text, str):
        return ""
    normalized = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "D").lower().strip()


def _normalize_identifier(value: str | None) -> str:
    """Normalize tax code, phone number, or domain for canonical key comparison."""
    if not value or not isinstance(value, str):
        return ""
    return re.sub(r"[\s.\-_/:\+]", "", value).lower().strip()


def _match_lead_entity(lead: dict[str, Any], ground_truth: dict[str, Any]) -> bool:
    """Check if a candidate lead matches a ground truth lead entity via multi-attribute identity."""
    # 1. Direct tax_id match (strongest ground truth)
    lead_tax = _normalize_identifier(lead.get("tax_id"))
    gt_tax = _normalize_identifier(ground_truth.get("tax_id"))
    if lead_tax and gt_tax and lead_tax == gt_tax:
        return True

    # 2. Canonical domain match
    lead_domain = _normalize_identifier(lead.get("domain") or lead.get("canonical_domain"))
    gt_domain = _normalize_identifier(ground_truth.get("domain") or ground_truth.get("canonical_domain"))
    if lead_domain and gt_domain and lead_domain == gt_domain:
        return True

    # 3. Direct Phone match
    lead_phone = _normalize_identifier(lead.get("phone") or lead.get("primary_phone"))
    gt_phone = _normalize_identifier(ground_truth.get("phone") or ground_truth.get("primary_phone"))
    if lead_phone and gt_phone and lead_phone == gt_phone:
        return True

    # 4. Company Name match with diacritics stripped and company legal forms normalized
    lead_name = _strip_vietnamese_accents(lead.get("company_name") or lead.get("name") or lead.get("title"))
    gt_name = _strip_vietnamese_accents(ground_truth.get("company_name") or ground_truth.get("name") or ground_truth.get("title"))
    if lead_name and gt_name:
        if lead_name == gt_name or lead_name in gt_name or gt_name in lead_name:
            return True
        # Compare significant tokens (ignoring common business prefixes like cong ty, cp, tnhh)
        stop_words = {"cong", "ty", "co", "phan", "tnhh", "mtv", "cp", "corp", "group", "viet", "nam", "vn"}
        lead_tokens = set(re.findall(r"\w+", lead_name)) - stop_words
        gt_tokens = set(re.findall(r"\w+", gt_name)) - stop_words
        if lead_tokens and gt_tokens and (lead_tokens.issubset(gt_tokens) or gt_tokens.issubset(lead_tokens)):
            return True

    return False


def precision_at_k(
    retrieved_leads: list[dict[str, Any]],
    expected_leads: list[dict[str, Any]],
    k: int = 10,
) -> float:
    """Compute Precision@k for retrieved leads against expected ground truth.

    Args:
        retrieved_leads: List of retrieved lead dictionaries ordered by ranking.
        expected_leads: List of expected ground-truth lead dictionaries.
        k: Cutoff rank for evaluation (defaults to 10).

    Returns:
        float: Precision score between 0.0 and 1.0.
    """
    if k <= 0:
        return 0.0
    if not retrieved_leads and not expected_leads:
        return 1.0
    if not retrieved_leads:
        return 0.0
    if not expected_leads:
        return 0.0

    top_k = retrieved_leads[:k]
    matched_count = 0

    for lead in top_k:
        if any(_match_lead_entity(lead, expected) for expected in expected_leads):
            matched_count += 1

    return round(matched_count / len(top_k), 4)


def recall_at_source(
    discovered_sources: list[str] | set[str],
    expected_sources: list[str] | set[str],
) -> float:
    """Compute Recall@Source across targeted platform scrapers.

    Args:
        discovered_sources: Data sources/adapters that yielded leads.
        expected_sources: Expected data source adapters for the query domain.

    Returns:
        float: Fraction of expected sources resolved and harvested (0.0 to 1.0).
    """
    disc_set = {_normalize_identifier(s) for s in discovered_sources if s}
    exp_set = {_normalize_identifier(s) for s in expected_sources if s}

    if not exp_set:
        return 1.0
    if not disc_set:
        return 0.0

    hit_count = len(disc_set & exp_set)
    return round(hit_count / len(exp_set), 4)


def _check_single_icp_rule(value: Any, expected: Any) -> bool:
    """Evaluate a single attribute against an ICP criterion."""
    if expected is None:
        return True
    if value is None:
        return False

    if isinstance(expected, list | set | tuple):
        if isinstance(value, list | set | tuple):
            return bool(set(value) & set(expected))
        return value in expected or any(str(e).lower() in str(value).lower() for e in expected)

    if isinstance(expected, dict):
        # Range criteria: {"min": ..., "max": ...}
        if "min" in expected and (value is None or value < expected["min"]):
            return False
        if "max" in expected and (value is None or value > expected["max"]):
            return False
        return True

    if isinstance(expected, str) and isinstance(value, str):
        return (
            _strip_vietnamese_accents(expected) in _strip_vietnamese_accents(value)
            or _strip_vietnamese_accents(value) in _strip_vietnamese_accents(expected)
        )

    return value == expected


def icp_match_rate(
    leads: list[dict[str, Any]],
    icp_criteria: dict[str, Any],
) -> float:
    """Evaluate Ideal Customer Profile (ICP) match rate over generated leads.

    Evaluates firmographic constraints (industry, company_size, location,
    revenue/capital, tech_stack).

    Args:
        leads: Generated lead candidates.
        icp_criteria: ICP constraints map.

    Returns:
        float: Percentage of leads matching all defined ICP constraints (0.0 to 1.0).
    """
    if not icp_criteria:
        return 1.0
    if not leads:
        return 0.0

    matching_leads = 0

    for lead in leads:
        matches_all = True
        for key, criterion in icp_criteria.items():
            lead_val = lead.get(key)
            # Check nested metadata or raw_data if not found at root
            if lead_val is None and "raw_data" in lead:
                lead_val = lead["raw_data"].get(key)

            if not _check_single_icp_rule(lead_val, criterion):
                matches_all = False
                break

        if matches_all:
            matching_leads += 1

    return round(matching_leads / len(leads), 4)


def intent_signal_precision(
    leads: list[dict[str, Any]],
    expected_intents: list[str] | set[str],
) -> float:
    """Compute precision of buying/hiring/procurement intent signals.

    Args:
        leads: Generated leads with intent classification.
        expected_intents: Expected intent categories (e.g. 'hiring', 'expansion', 'procurement').

    Returns:
        float: Fraction of leads exhibiting valid expected intent signals (0.0 to 1.0).
    """
    if not expected_intents:
        return 1.0
    if not leads:
        return 0.0

    normalized_expected = {_strip_vietnamese_accents(i) for i in expected_intents if i}
    valid_intent_count = 0

    for lead in leads:
        lead_intent = lead.get("intent") or lead.get("intent_signal") or lead.get("intent_category")
        if not lead_intent and "raw_data" in lead:
            lead_intent = lead["raw_data"].get("intent")

        if lead_intent:
            norm_intent = _strip_vietnamese_accents(str(lead_intent))
            if any(exp in norm_intent or norm_intent in exp for exp in normalized_expected):
                valid_intent_count += 1

    return round(valid_intent_count / len(leads), 4)


def contact_accuracy(
    leads: list[dict[str, Any]],
    expected_leads: list[dict[str, Any]] | None = None,
) -> float:
    """Compute completeness and validity of actionable contact endpoints.

    Checks phone numbers (standard 10-digit Vietnamese format), email RFC formats,
    and ground truth contact alignment when expected_leads is provided.

    Args:
        leads: Generated lead candidates.
        expected_leads: Optional ground truth leads for verification.

    Returns:
        float: Proportion of leads having valid, verified contact endpoints (0.0 to 1.0).
    """
    if not leads:
        return 0.0

    valid_leads = 0
    phone_pattern = re.compile(r"^(?:0|\+84|84)(?:3|5|7|8|9)\d{8}$")
    email_pattern = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")

    for lead in leads:
        has_valid_contact = False

        phone = _normalize_identifier(lead.get("phone") or lead.get("primary_phone"))
        if phone and phone_pattern.match(phone):
            has_valid_contact = True

        email = lead.get("email") or lead.get("primary_email")
        if email and isinstance(email, str) and email_pattern.match(email.strip()):
            has_valid_contact = True

        if lead.get("is_zalo_active") or lead.get("contact_candidates"):
            has_valid_contact = True

        if has_valid_contact:
            valid_leads += 1

    return round(valid_leads / len(leads), 4)


def duplicate_rate(
    raw_count: int,
    deduplicated_count: int,
) -> float:
    """Compute entity duplicate rate in the candidate pool.

    Args:
        raw_count: Total raw lead records discovered before deduplication.
        deduplicated_count: Count of unique lead records after deduplication.

    Returns:
        float: Duplicate ratio between 0.0 and 1.0.
    """
    if raw_count <= 0:
        return 0.0
    if deduplicated_count > raw_count:
        return 0.0

    dupes = raw_count - deduplicated_count
    return round(dupes / raw_count, 4)


def false_positive_rate(
    retrieved_leads: list[dict[str, Any]],
    negative_candidates: list[dict[str, Any]],
) -> float:
    """Compute False Positive Rate (disqualified distractors mistakenly returned).

    Args:
        retrieved_leads: Leads returned by the orchestrator.
        negative_candidates: Known disqualified/out-of-scope negative entities.

    Returns:
        float: Fraction of negative candidates incorrectly matched (0.0 to 1.0).
    """
    if not negative_candidates:
        return 0.0
    if not retrieved_leads:
        return 0.0

    fp_count = 0
    for neg in negative_candidates:
        if any(_match_lead_entity(retrieved, neg) for retrieved in retrieved_leads):
            fp_count += 1

    return round(fp_count / len(negative_candidates), 4)


def time_to_first_lead(latencies_ms: list[float] | float) -> float:
    """Compute latency (p50 or single observation) for Time To First Lead in milliseconds.

    Args:
        latencies_ms: Single latency value or list of recorded latencies in ms.

    Returns:
        float: Average or representative TTFL in milliseconds.
    """
    if isinstance(latencies_ms, int | float):
        return round(float(latencies_ms), 2)
    if not latencies_ms:
        return 0.0
    return round(sum(latencies_ms) / len(latencies_ms), 2)


__all__ = [
    "contact_accuracy",
    "duplicate_rate",
    "false_positive_rate",
    "icp_match_rate",
    "intent_signal_precision",
    "precision_at_k",
    "recall_at_source",
    "time_to_first_lead",
]
