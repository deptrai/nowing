"""Tests for InboundIntentClassifier and is_researchy (AI-39.9)."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.main_agent.classifier import (
    _is_researchy,
    is_researchy,
)
from app.services.auto_reply_agent import InboundIntentClassifier


@pytest.mark.unit
def test_regex_is_researchy():
    assert _is_researchy("Phân tích chi tiết thị trường Q7 và Thủ Thiêm")
    assert _is_researchy("Tìm kiếm tài liệu tổng quan ngành")
    assert not _is_researchy("Chào bạn")


@pytest.mark.unit
async def test_is_researchy_fallback_when_disabled(monkeypatch):
    monkeypatch.setattr("app.config.decision.decision_enabled", lambda: False)
    assert await is_researchy("Nghiên cứu thị trường bất động sản")
    assert not await is_researchy("Xin chào")


@pytest.mark.unit
async def test_is_researchy_via_decision_service(monkeypatch):
    monkeypatch.setattr("app.config.decision.decision_enabled", lambda: True)
    monkeypatch.setattr(
        "app.config.decision.decision_task_enabled", lambda task: task == "intent"
    )

    async def _mock_classify(text, **kwargs):
        if "nghiên cứu" in text.lower():
            return {"label": "search", "confidence": 0.85}
        return {"label": "chitchat", "confidence": 0.95}

    monkeypatch.setattr(
        "app.services.intent_classification.classify_intent",
        _mock_classify,
    )

    assert await is_researchy("Nghiên cứu thị trường")
    assert not await is_researchy("Xin chào shop")


@pytest.mark.unit
async def test_is_researchy_fallback_on_error(monkeypatch):
    monkeypatch.setattr("app.config.decision.decision_enabled", lambda: True)
    monkeypatch.setattr(
        "app.config.decision.decision_task_enabled", lambda task: task == "intent"
    )

    async def _failing_classify(text, **kwargs):
        raise RuntimeError("Decision service connection error")

    monkeypatch.setattr(
        "app.services.intent_classification.classify_intent",
        _failing_classify,
    )

    # Falls back to regex
    assert await is_researchy("Nghiên cứu thị trường")
    assert not await is_researchy("Xin chào shop")


@pytest.mark.unit
async def test_inbound_intent_classifier_aevaluate_intent_jev(monkeypatch):
    classifier = InboundIntentClassifier()

    monkeypatch.setattr("app.config.decision.decision_enabled", lambda: True)
    monkeypatch.setattr(
        "app.config.decision.decision_task_enabled", lambda task: task == "intent"
    )

    async def _mock_classify(text, **kwargs):
        if "mua ngay" in text.lower():
            return {"label": "action", "confidence": 0.95}
        if "tư vấn" in text.lower():
            return {"label": "recommendation", "confidence": 0.88}
        return {"label": "chitchat", "confidence": 0.90}

    monkeypatch.setattr(
        "app.services.intent_classification.classify_intent",
        _mock_classify,
    )

    score, reason, is_hot = await classifier.aevaluate_intent(
        "Tôi muốn mua ngay căn này"
    )
    assert score == 0.95
    assert is_hot is True
    assert "Jev" in reason

    score, reason, is_hot = await classifier.aevaluate_intent("Em tư vấn giúp anh nhé")
    assert score == 0.85
    assert is_hot is True
    assert "Jev" in reason

    score, reason, is_hot = await classifier.aevaluate_intent(
        "Thời tiết hôm nay đẹp nhỉ"
    )
    assert score == 0.20
    assert is_hot is False


@pytest.mark.unit
async def test_inbound_intent_classifier_fallback_on_error(monkeypatch):
    classifier = InboundIntentClassifier()

    monkeypatch.setattr("app.config.decision.decision_enabled", lambda: True)
    monkeypatch.setattr(
        "app.config.decision.decision_task_enabled", lambda task: task == "intent"
    )

    async def _failing_classify(text, **kwargs):
        raise RuntimeError("Jev timeout")

    monkeypatch.setattr(
        "app.services.intent_classification.classify_intent",
        _failing_classify,
    )

    score, _reason, is_hot = await classifier.aevaluate_intent(
        "Gửi tôi báo giá và đặt cọc ngay"
    )
    # Regex fallback catches "báo giá" and "đặt cọc"
    assert is_hot is True
    assert score >= 0.80
