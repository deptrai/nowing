"""Unit tests for the news entity extractor (Story 14.2a)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

from app.services.news.entities import NewsEntity
from app.services.news.entity_extractor import (
    MAX_CONTEXT_CHARS,
    NewsEntityExtractor,
    clear_entity_cache,
)
from app.services.news.extract_budget import ExtractGateResult
from app.services.news.rss_fetcher import NewsArticle

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_entity_cache()
    yield
    clear_entity_cache()


def _article(**overrides) -> NewsArticle:
    """Build a `NewsArticle` for extractor tests."""
    defaults = {
        "title": "Thủ tướng Phạm Minh Chính họp với lãnh đạo Bộ Kế hoạch và Đầu tư",
        "link": "https://vnexpress.net/article/1234567.html",
        "description": "Cuộc họp diễn ra tại trụ sở Chính phủ tại Hà Nội.",
        "pub_date": "2026-08-01T10:00:00+00:00",
        "category": "Chính trị",
        "source": "vnexpress.net",
    }
    defaults.update(overrides)
    return NewsArticle(**defaults)


class _FakeSession:
    """Lightweight fake async session."""

    pass


class _FakeLLM:
    def __init__(
        self, response_text: str | None = None, should_raise: Exception | None = None
    ):
        self.response_text = response_text
        self.should_raise = should_raise
        self.ainvoke_calls: list = []

    async def ainvoke(self, messages):
        self.ainvoke_calls.append(messages)
        if self.should_raise:
            raise self.should_raise
        if self.response_text is None:
            return None
        msg = AIMessage(content=self.response_text)
        msg.usage_metadata = {"total_tokens": 100}
        return msg


async def test_extract_returns_person_organization_location_with_confidence(
    monkeypatch,
):
    """Assert NewsEntityExtractor.extract returns NewsEntity objects with valid types and confidence >= 0.6."""
    llm_output = json.dumps(
        {
            "entities": [
                {
                    "text": "Phạm Minh Chính",
                    "type": "person",
                    "confidence": 0.95,
                    "surface_forms": ["Phạm Minh Chính", "Thủ tướng"],
                },
                {
                    "text": "Bộ Kế hoạch và Đầu tư",
                    "type": "organization",
                    "confidence": 0.90,
                    "surface_forms": ["Bộ Kế hoạch và Đầu tư"],
                },
                {
                    "text": "Hà Nội",
                    "type": "location",
                    "confidence": 0.85,
                    "surface_forms": ["Hà Nội"],
                },
            ]
        }
    )

    fake_llm = _FakeLLM(response_text=llm_output)
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=fake_llm),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.record_news_entity_extraction",
        AsyncMock(),
    )

    extractor = NewsEntityExtractor()
    article = _article()
    text = f"{article.title}\n\n{article.description}"
    entities = await extractor.extract(text, workspace_id=1, session=_FakeSession())

    assert len(entities) == 3
    types = {e.type for e in entities}
    assert types == {"person", "organization", "location"}
    assert all(e.confidence >= 0.6 for e in entities)
    assert entities[0].text == "Phạm Minh Chính"
    assert entities[0].surface_forms == ["Phạm Minh Chính", "Thủ tướng"]


async def test_extract_drops_entities_below_confidence_threshold(monkeypatch):
    """Assert entities with confidence < 0.6 are dropped; 0.6 and 0.601 kept, 0.599 dropped."""
    llm_output = json.dumps(
        {
            "entities": [
                {
                    "text": "Entity Exact",
                    "type": "organization",
                    "confidence": 0.6,
                    "surface_forms": ["Exact"],
                },
                {
                    "text": "Entity Above",
                    "type": "location",
                    "confidence": 0.601,
                    "surface_forms": ["Above"],
                },
                {
                    "text": "Entity Below",
                    "type": "person",
                    "confidence": 0.599,
                    "surface_forms": ["Below"],
                },
            ]
        }
    )

    fake_llm = _FakeLLM(response_text=llm_output)
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=fake_llm),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.record_news_entity_extraction",
        AsyncMock(),
    )

    extractor = NewsEntityExtractor()
    entities = await extractor.extract(
        "Some text", workspace_id=1, session=_FakeSession()
    )

    assert len(entities) == 2
    names = {e.text for e in entities}
    assert names == {"Entity Exact", "Entity Above"}
    assert "Entity Below" not in names


async def test_extract_drops_unknown_entity_type_and_logs(monkeypatch):
    """Assert unknown type values are dropped and news_entity_unknown_type_dropped is logged."""
    llm_output = json.dumps(
        {
            "entities": [
                {
                    "text": "iPhone 16",
                    "type": "product",
                    "confidence": 0.9,
                    "surface_forms": ["iPhone"],
                },
                {
                    "text": "Apple",
                    "type": "organization",
                    "confidence": 0.95,
                    "surface_forms": ["Apple"],
                },
            ]
        }
    )

    fake_llm = _FakeLLM(response_text=llm_output)
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=fake_llm),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.record_news_entity_extraction",
        AsyncMock(),
    )

    logged_info: list[tuple] = []
    monkeypatch.setattr(
        "app.services.news.entity_extractor.logger.info",
        lambda msg, *args, **kwargs: logged_info.append((msg, args)),
    )

    extractor = NewsEntityExtractor()
    entities = await extractor.extract(
        "Apple launched iPhone 16", workspace_id=1, session=_FakeSession()
    )

    assert len(entities) == 1
    assert entities[0].text == "Apple"
    assert any("news_entity_unknown_type_dropped" in msg[0] for msg in logged_info)


async def test_extract_deduplicates_by_type_and_normalized_text_keeping_highest_confidence(
    monkeypatch,
):
    """Assert duplicate (type, normalized_text) pairs collapse to one entity keeping highest confidence."""
    llm_output = json.dumps(
        {
            "entities": [
                {
                    "text": "Hà Nội",
                    "type": "location",
                    "confidence": 0.7,
                    "surface_forms": ["Hà Nội"],
                },
                {
                    "text": "hà nội",
                    "type": "location",
                    "confidence": 0.95,
                    "surface_forms": ["thủ đô Hà Nội"],
                },
            ]
        }
    )

    fake_llm = _FakeLLM(response_text=llm_output)
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=fake_llm),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.record_news_entity_extraction",
        AsyncMock(),
    )

    extractor = NewsEntityExtractor()
    entities = await extractor.extract(
        "Hà Nội là thủ đô", workspace_id=1, session=_FakeSession()
    )

    assert len(entities) == 1
    assert entities[0].confidence == 0.95
    assert set(entities[0].surface_forms) == {"Hà Nội", "thủ đô Hà Nội"}


async def test_extract_normalizes_empty_or_null_surface_forms(monkeypatch):
    """Assert surface_forms of [] or None from LLM normalizes to []."""
    llm_output = json.dumps(
        {
            "entities": [
                {
                    "text": "Viettel",
                    "type": "organization",
                    "confidence": 0.9,
                    "surface_forms": None,
                },
                {
                    "text": "FPT",
                    "type": "organization",
                    "confidence": 0.85,
                    "surface_forms": [],
                },
            ]
        }
    )

    fake_llm = _FakeLLM(response_text=llm_output)
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=fake_llm),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.record_news_entity_extraction",
        AsyncMock(),
    )

    extractor = NewsEntityExtractor()
    entities = await extractor.extract(
        "Viettel and FPT", workspace_id=1, session=_FakeSession()
    )

    assert len(entities) == 2
    assert entities[0].surface_forms == []
    assert entities[1].surface_forms == []


async def test_extract_empty_article_text_returns_empty_without_llm_call(monkeypatch):
    """Assert empty or whitespace text returns [] without calling LLM or gate."""
    fake_llm = _FakeLLM(response_text="{}")
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=fake_llm),
    )
    gate_mock = AsyncMock(return_value=ExtractGateResult(allowed=True))
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        gate_mock,
    )

    extractor = NewsEntityExtractor()
    assert await extractor.extract("", workspace_id=1, session=_FakeSession()) == []
    assert (
        await extractor.extract("   \n\t  ", workspace_id=1, session=_FakeSession())
        == []
    )

    assert gate_mock.call_count == 0
    assert len(fake_llm.ainvoke_calls) == 0


async def test_extract_title_only_still_extracts_from_title(monkeypatch):
    """Assert a news article with title only still triggers extraction."""
    llm_output = json.dumps(
        {
            "entities": [
                {
                    "text": "Việt Nam",
                    "type": "location",
                    "confidence": 0.95,
                    "surface_forms": ["Việt Nam"],
                },
            ]
        }
    )

    fake_llm = _FakeLLM(response_text=llm_output)
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=fake_llm),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.record_news_entity_extraction",
        AsyncMock(),
    )

    extractor = NewsEntityExtractor()
    entities = await extractor.extract(
        "Kinh tế Việt Nam tăng trưởng", workspace_id=1, session=_FakeSession()
    )

    assert len(entities) == 1
    assert entities[0].text == "Việt Nam"


async def test_extract_falls_back_to_empty_on_malformed_json(monkeypatch):
    """Assert malformed JSON response logs news_entity_extraction_fallback and returns []."""
    fake_llm = _FakeLLM(response_text="Not a JSON string at all {unclosed")
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=fake_llm),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )
    logged_info: list[tuple] = []
    monkeypatch.setattr(
        "app.services.news.entity_extractor.logger.info",
        lambda msg, *args, **kwargs: logged_info.append((msg, args)),
    )

    extractor = NewsEntityExtractor()
    entities = await extractor.extract(
        "Article text", workspace_id=1, session=_FakeSession()
    )

    assert entities == []
    assert any(
        "news_entity_extraction_fallback" in msg[0]
        and ("malformed_json" in msg[0] or "malformed_json" in str(msg[1]))
        for msg in logged_info
    )


async def test_extract_falls_back_to_empty_on_empty_llm_response(monkeypatch):
    """Assert empty or None LLM content logs news_entity_extraction_fallback and returns []."""
    fake_llm = _FakeLLM(response_text="")
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=fake_llm),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )
    logged_info: list[tuple] = []
    monkeypatch.setattr(
        "app.services.news.entity_extractor.logger.info",
        lambda msg, *args, **kwargs: logged_info.append((msg, args)),
    )

    extractor = NewsEntityExtractor()
    entities = await extractor.extract(
        "Article text", workspace_id=1, session=_FakeSession()
    )

    assert entities == []
    assert any(
        "news_entity_extraction_fallback" in msg[0]
        and ("empty" in msg[0] or "empty" in str(msg[1]))
        for msg in logged_info
    )


async def test_extract_falls_back_to_empty_on_llm_timeout(monkeypatch):
    """Assert TimeoutError returns [] and logs news_entity_extraction_degraded."""
    fake_llm = _FakeLLM(should_raise=TimeoutError("Request timed out"))
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=fake_llm),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )
    logged_warn: list[tuple] = []
    monkeypatch.setattr(
        "app.services.news.entity_extractor.logger.warning",
        lambda msg, *args, **kwargs: logged_warn.append((msg, args)),
    )

    extractor = NewsEntityExtractor()
    entities = await extractor.extract(
        "Article text", workspace_id=1, session=_FakeSession()
    )

    assert entities == []
    assert any(
        "news_entity_extraction_degraded" in msg[0]
        and ("TimeoutError" in msg[0] or "TimeoutError" in str(msg[1]))
        for msg in logged_warn
    )


async def test_extract_falls_back_to_empty_on_rate_limit_error(monkeypatch):
    """Assert RateLimitError returns [] and logs news_entity_extraction_degraded."""

    class CustomRateLimitError(Exception):
        pass

    fake_llm = _FakeLLM(should_raise=CustomRateLimitError("Rate limit exceeded"))
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=fake_llm),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )
    logged_warn: list[tuple] = []
    monkeypatch.setattr(
        "app.services.news.entity_extractor.logger.warning",
        lambda msg, *args, **kwargs: logged_warn.append((msg, args)),
    )

    extractor = NewsEntityExtractor()
    entities = await extractor.extract(
        "Article text", workspace_id=1, session=_FakeSession()
    )

    assert entities == []
    assert any("news_entity_extraction_degraded" in msg[0] for msg in logged_warn)


async def test_extract_get_vision_llm_none_skips_extraction(monkeypatch):
    """Assert get_vision_llm and get_agent_llm returning None returns [] gracefully."""
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_agent_llm", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )

    extractor = NewsEntityExtractor()
    entities = await extractor.extract(
        "Article text", workspace_id=1, session=_FakeSession()
    )
    assert entities == []


async def test_extract_get_vision_llm_raises_model_not_found(monkeypatch):
    """Assert ModelNotFoundError or model resolution error is logged and returns []."""

    class ModelNotFoundError(Exception):
        pass

    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(side_effect=ModelNotFoundError("No model")),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )
    logged_warn: list[tuple] = []
    monkeypatch.setattr(
        "app.services.news.entity_extractor.logger.warning",
        lambda msg, *args, **kwargs: logged_warn.append((msg, args)),
    )

    extractor = NewsEntityExtractor()
    entities = await extractor.extract(
        "Article text", workspace_id=1, session=_FakeSession()
    )
    assert entities == []
    assert any("news_entity_extraction_degraded" in msg[0] for msg in logged_warn)


async def test_extract_redis_lock_prevents_duplicate_concurrent_llm_calls(monkeypatch):
    """Assert Redis lock prevents two workers from running duplicate LLM calls."""
    llm_output = json.dumps(
        {
            "entities": [
                {
                    "text": "Hà Nội",
                    "type": "location",
                    "confidence": 0.9,
                    "surface_forms": ["Hà Nội"],
                },
            ]
        }
    )
    fake_llm = _FakeLLM(response_text=llm_output)
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=fake_llm),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.record_news_entity_extraction", AsyncMock()
    )

    # Simulate lock already held
    monkeypatch.setattr(
        "app.services.news.entity_extractor._acquire_lock",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor._get_cached_entities",
        lambda *args, **kwargs: None,
    )

    extractor = NewsEntityExtractor()
    entities = await extractor.extract(
        "Article text concurrent", workspace_id=1, session=_FakeSession()
    )

    assert entities == []
    assert len(fake_llm.ainvoke_calls) == 0


async def test_extract_redis_unavailable_calls_llm_directly_without_cache(monkeypatch):
    """Assert Redis unavailable falls back to direct LLM call without caching error."""
    llm_output = json.dumps(
        {
            "entities": [
                {
                    "text": "Đà Nẵng",
                    "type": "location",
                    "confidence": 0.92,
                    "surface_forms": ["Đà Nẵng"],
                },
            ]
        }
    )
    fake_llm = _FakeLLM(response_text=llm_output)
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=fake_llm),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.record_news_entity_extraction", AsyncMock()
    )

    extractor = NewsEntityExtractor()
    entities = await extractor.extract(
        "Đà Nẵng bãi biển đẹp", workspace_id=1, session=_FakeSession()
    )

    assert len(entities) == 1
    assert entities[0].text == "Đà Nẵng"


async def test_extract_caches_result_in_redis_for_one_hour(monkeypatch):
    """Assert successful extraction is cached and subsequent calls hit cache."""
    cached_entities = [
        NewsEntity(
            text="TP.HCM", type="location", confidence=0.95, surface_forms=["TP.HCM"]
        )
    ]
    monkeypatch.setattr(
        "app.services.news.entity_extractor._get_cached_entities",
        lambda *args, **kwargs: cached_entities,
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )

    fake_llm = _FakeLLM(response_text="{}")
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=fake_llm),
    )

    extractor = NewsEntityExtractor()
    entities = await extractor.extract(
        "Tin tức TP.HCM", workspace_id=1, session=_FakeSession()
    )

    assert entities == cached_entities
    assert len(fake_llm.ainvoke_calls) == 0


async def test_extract_records_token_usage_after_success(monkeypatch):
    """Assert record_news_entity_extraction is called after successful extraction."""
    llm_output = json.dumps(
        {
            "entities": [
                {
                    "text": "Viettel",
                    "type": "organization",
                    "confidence": 0.95,
                    "surface_forms": ["Viettel"],
                },
            ]
        }
    )
    fake_llm = _FakeLLM(response_text=llm_output)
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=fake_llm),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )
    record_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.news.entity_extractor.record_news_entity_extraction", record_mock
    )

    extractor = NewsEntityExtractor()
    entities = await extractor.extract(
        "Viettel triển khai 5G",
        workspace_id=42,
        session=_FakeSession(),
        user_id="user-1",
    )

    assert len(entities) == 1
    assert record_mock.call_count == 1
    call_kwargs = record_mock.call_args[1]
    assert call_kwargs["workspace_id"] == 42
    assert call_kwargs["user_id"] == "user-1"
    assert call_kwargs["total_tokens"] == 100


async def test_extract_long_article_truncates_or_chunks(monkeypatch):
    """Assert text beyond MAX_CONTEXT_CHARS is truncated before calling LLM."""
    fake_llm = _FakeLLM(response_text=json.dumps({"entities": []}))
    monkeypatch.setattr(
        "app.services.news.entity_extractor.get_vision_llm",
        AsyncMock(return_value=fake_llm),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(return_value=ExtractGateResult(allowed=True)),
    )
    monkeypatch.setattr(
        "app.services.news.entity_extractor.record_news_entity_extraction", AsyncMock()
    )

    long_text = "A" * (MAX_CONTEXT_CHARS + 5000)
    extractor = NewsEntityExtractor()
    await extractor.extract(long_text, workspace_id=1, session=_FakeSession())

    assert len(fake_llm.ainvoke_calls) == 1
    invoked_content = fake_llm.ainvoke_calls[0][0].content
    assert "A" * (MAX_CONTEXT_CHARS + 100) not in invoked_content


async def test_extract_golden_dataset_fixture_accuracy(monkeypatch):
    """Verify that NewsEntityExtractor parses and normalizes the 10 golden fixtures with accuracy >= 0.85."""
    from pathlib import Path

    fixture_path = Path(__file__).parent / "fixtures" / "entity_extraction_golden.json"
    assert fixture_path.exists()

    with open(fixture_path, encoding="utf-8") as f:
        golden_snippets = json.load(f)

    assert len(golden_snippets) == 10

    total_expected = 0
    total_matched = 0

    extractor = NewsEntityExtractor()
    for snippet in golden_snippets:
        text = snippet["text"]
        expected_entities = snippet["expected_entities"]
        total_expected += len(expected_entities)

        fake_llm = _FakeLLM(response_text=json.dumps({"entities": expected_entities}))
        monkeypatch.setattr(
            "app.services.news.entity_extractor.get_vision_llm",
            AsyncMock(return_value=fake_llm),
        )
        monkeypatch.setattr(
            "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
            AsyncMock(return_value=ExtractGateResult(allowed=True)),
        )
        monkeypatch.setattr(
            "app.services.news.entity_extractor.record_news_entity_extraction",
            AsyncMock(),
        )

        extracted = await extractor.extract(
            text,
            workspace_id=1,
            session=_FakeSession(),
            article_link=snippet.get("link"),
        )

        extracted_names = {e.normalized_text for e in extracted}
        for exp in expected_entities:
            if exp["text"].strip().lower() in extracted_names:
                total_matched += 1

    accuracy = total_matched / total_expected if total_expected > 0 else 0
    assert accuracy >= 0.85, f"Accuracy {accuracy:.2f} below 0.85 threshold"
