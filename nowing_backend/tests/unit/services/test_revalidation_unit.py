"""Unit tests for revalidation helpers (Story 9.6c)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.services.memory.revalidation_service import _extract_text, _normalize

pytestmark = [pytest.mark.unit]


class _AnswerOutput(BaseModel):
    answer: str


class _ItemsOutput(BaseModel):
    items: list


class _DictOutput(BaseModel):
    answer: str | None = None
    items: list | None = None

    def model_dump(self, **kwargs):
        return {"answer": self.answer, "items": self.items}


def test_extract_text_returns_answer_from_basemodel():
    output = _AnswerOutput(answer="Widget costs 19.99 USD")
    assert _extract_text(output, "reddit.scrape") == "Widget costs 19.99 USD"


def test_extract_text_joins_items_from_basemodel():
    output = _ItemsOutput(items=[{"a": 1}, {"b": 2}])
    text = _extract_text(output, "reddit.scrape")
    assert '"a": 1' in text
    assert '"b": 2' in text


def test_extract_text_json_dump_for_basemodel_without_answer_or_items():
    class _PlainOutput(BaseModel):
        status: str = "ok"

    output = _PlainOutput()
    text = _extract_text(output, "reddit.scrape")
    assert '"status": "ok"' in text


def test_extract_text_returns_answer_from_plain_object_model_dump():
    output = _DictOutput(answer="Widget costs 19.99 USD")
    assert _extract_text(output, "reddit.scrape") == "Widget costs 19.99 USD"


def test_extract_text_returns_answer_from_dict():
    output = {"answer": "Widget costs 19.99 USD"}
    assert _extract_text(output, "reddit.scrape") == "Widget costs 19.99 USD"


def test_extract_text_joins_items_from_dict():
    output = {"items": [{"a": 1}, {"b": 2}]}
    text = _extract_text(output, "reddit.scrape")
    assert '"a": 1' in text
    assert '"b": 2' in text


def test_extract_text_returns_str_for_arbitrary_object():
    output = object()
    assert _extract_text(output, "reddit.scrape") == str(output)


def test_extract_text_handles_model_dump_exception():
    class BadModel:
        def model_dump(self, **kwargs):
            raise RuntimeError("dump failed")

    output = BadModel()
    assert _extract_text(output, "reddit.scrape") == str(output)


def test_extract_text_handles_items_with_non_dict_elements():
    output = {"items": ["plain string", 123]}
    text = _extract_text(output, "reddit.scrape")
    assert "plain string" in text
    assert "123" in text


def test_extract_text_ensure_ascii_false_preserves_unicode_in_basemodel_items():
    class _UnicodeItems(BaseModel):
        items: list

    output = _UnicodeItems(items=[{"name": "Nguyễn"}])
    text = _extract_text(output, "reddit.scrape")
    assert "Nguyễn" in text


def test_extract_text_ensure_ascii_false_preserves_unicode_in_dict_items():
    output = {"items": [{"name": "Nguyễn"}]}
    text = _extract_text(output, "reddit.scrape")
    assert "Nguyễn" in text


def test_extract_text_exclude_none_true_skips_none_answer():
    class _NullableAnswer(BaseModel):
        answer: str | None = None
        other: str = "ok"

    output = _NullableAnswer()
    text = _extract_text(output, "reddit.scrape")
    assert '"other": "ok"' in text
    assert "answer" not in text


def test_extract_text_plain_object_model_dump_returns_list():
    import json

    class _ListDump:
        def model_dump(self, **kwargs):
            return ["answer", "value"]

    output = _ListDump()
    assert _extract_text(output, "reddit.scrape") == json.dumps(["answer", "value"])


def test_extract_text_basemodel_uses_ensure_ascii_false_for_unicode_dump():
    class _UnicodePlain(BaseModel):
        status: str = "Tốt"

    output = _UnicodePlain()
    assert "Tốt" in _extract_text(output, "reddit.scrape")


def test_extract_text_dict_uses_ensure_ascii_false_for_unicode_dump():
    output = {"status": "Tốt"}
    assert "Tốt" in _extract_text(output, "reddit.scrape")


def test_extract_text_joins_items_exact_format():
    output = {"items": [{"a": 1}, {"b": 2}]}
    assert _extract_text(output, "reddit.scrape") == '{"a": 1}\n{"b": 2}'


def test_extract_text_basemodel_items_not_list_returns_full_json():
    import json

    class _BadItems(BaseModel):
        items: str = "not a list"

    output = _BadItems()
    assert _extract_text(output, "reddit.scrape") == json.dumps({"items": "not a list"})


def test_extract_text_plain_object_items_not_list_returns_full_json():
    import json

    class _BadItems:
        def model_dump(self, **kwargs):
            return {"items": "not a list"}

    output = _BadItems()
    assert _extract_text(output, "reddit.scrape") == json.dumps({"items": "not a list"})


def test_extract_text_plain_object_model_dump_uses_ensure_ascii_false():
    class _UnicodePlain:
        def model_dump(self, **kwargs):
            return {"status": "Tốt"}

    output = _UnicodePlain()
    assert "Tốt" in _extract_text(output, "reddit.scrape")


def test_extract_text_plain_object_items_uses_ensure_ascii_false():
    class _UnicodeItemsPlain:
        def model_dump(self, **kwargs):
            return {"items": [{"name": "Nguyễn"}]}

    output = _UnicodeItemsPlain()
    assert "Nguyễn" in _extract_text(output, "reddit.scrape")


def test_normalize_casefolds_and_collapses_whitespace():
    text = "  Widget   COSTS  19.99  USD  "
    assert _normalize(text) == "widget costs 19.99 usd"


def test_normalize_strips_leading_and_trailing_whitespace():
    text = "\t\nWidget costs 19.99 USD\n\t"
    assert _normalize(text) == "widget costs 19.99 usd"


def test_normalize_handles_empty_string():
    assert _normalize("") == ""


def test_normalize_handles_single_word():
    assert _normalize("WIDGET") == "widget"


def test_normalize_preserves_order_of_characters():
    text = "abc def"
    assert _normalize(text) == "abc def"
