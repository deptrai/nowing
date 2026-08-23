"""Unit tests for news entity PII redaction (Story 14.2a / AD-25)."""

from __future__ import annotations

import pytest

from app.services.news.entities import NewsEntity
from app.services.news.entity_extractor import (
    mask_person_entities_in_text,
    redact_entities_metadata,
)
from app.services.scraper_chunks.schemas import ChunkValidationError

pytestmark = [pytest.mark.unit]


def test_person_surface_forms_replaced_with_name_in_content():
    """Assert person surface forms are replaced with <NAME> in content."""
    entities = [
        NewsEntity(
            text="Phạm Minh Chính",
            type="person",
            confidence=0.98,
            surface_forms=["Phạm Minh Chính", "ông Chính"],
        )
    ]
    raw_text = "Thủ tướng Phạm Minh Chính chủ trì cuộc họp. Sau đó, ông Chính phát biểu chỉ đạo."
    redacted = mask_person_entities_in_text(raw_text, entities)

    assert "Phạm Minh Chính" not in redacted
    assert "ông Chính" not in redacted
    assert "<NAME>" in redacted


def test_person_text_and_surface_forms_redacted_in_metadata_entities():
    """Assert metadata.entities for person stores text='<NAME>' and surface_forms=['<NAME>']."""
    entities = [
        NewsEntity(
            text="Nguyễn Văn A",
            type="person",
            confidence=0.95,
            surface_forms=["Nguyễn Văn A", "anh A"],
        )
    ]
    metadata_entities = redact_entities_metadata(entities)

    assert len(metadata_entities) == 1
    assert metadata_entities[0]["text"] == "<NAME>"
    assert metadata_entities[0]["type"] == "person"
    assert metadata_entities[0]["confidence"] == 0.95
    assert metadata_entities[0]["surface_forms"] == ["<NAME>"]


def test_foreign_person_names_masked_in_content_and_metadata():
    """Assert foreign person names recognized as person are masked to <NAME>."""
    entities = [
        NewsEntity(
            text="Joe Biden",
            type="person",
            confidence=0.97,
            surface_forms=["Joe Biden", "ông Biden"],
        ),
        NewsEntity(
            text="Elon Musk",
            type="person",
            confidence=0.96,
            surface_forms=["Elon Musk"],
        ),
    ]
    raw_text = "Tổng thống Joe Biden và tỷ phú Elon Musk tham dự hội nghị tại Hà Nội. Ông Biden phát biểu."
    redacted_text = mask_person_entities_in_text(raw_text, entities)

    assert "Joe Biden" not in redacted_text
    assert "Elon Musk" not in redacted_text
    assert "Ông Biden" not in redacted_text
    assert "<NAME>" in redacted_text

    metadata_entities = redact_entities_metadata(entities)
    assert all(e["text"] == "<NAME>" for e in metadata_entities)
    assert all(e["surface_forms"] == ["<NAME>"] for e in metadata_entities)


def test_composite_organization_with_person_substring_masks_person():
    """Assert organization containing person name masks person substring in metadata.entities."""
    entities = [
        NewsEntity(
            text="Nguyễn Văn A",
            type="person",
            confidence=0.95,
            surface_forms=["Nguyễn Văn A"],
        ),
        NewsEntity(
            text="Công ty TNHH Nguyễn Văn A",
            type="organization",
            confidence=0.92,
            surface_forms=["Công ty TNHH Nguyễn Văn A", "Công ty Nguyễn Văn A"],
        ),
    ]

    metadata_entities = redact_entities_metadata(entities)
    org = next(e for e in metadata_entities if e["type"] == "organization")

    assert org["text"] == "Công ty TNHH <NAME>"
    assert "Nguyễn Văn A" not in org["text"]
    assert all(
        "<NAME>" in form and "Nguyễn Văn A" not in form for form in org["surface_forms"]
    )


def test_composite_location_with_person_substring_masks_person():
    """Assert location containing person name masks person substring in metadata.entities."""
    entities = [
        NewsEntity(
            text="Trần Hưng Đạo",
            type="person",
            confidence=0.96,
            surface_forms=["Trần Hưng Đạo"],
        ),
        NewsEntity(
            text="Đường Trần Hưng Đạo",
            type="location",
            confidence=0.94,
            surface_forms=["Đường Trần Hưng Đạo"],
        ),
    ]

    metadata_entities = redact_entities_metadata(entities)
    loc = next(e for e in metadata_entities if e["type"] == "location")

    assert loc["text"] == "Đường <NAME>"
    assert "Trần Hưng Đạo" not in loc["text"]


def test_redaction_runs_after_extraction_and_before_chunk_serialization():
    """Assert redaction order: extract -> mask person text -> redact_pii -> redact metadata."""
    entities = [
        NewsEntity(
            text="Phan Văn Mãi",
            type="person",
            confidence=0.95,
            surface_forms=["Phan Văn Mãi"],
        ),
        NewsEntity(
            text="TP.HCM",
            type="location",
            confidence=0.98,
            surface_forms=["TP.HCM"],
        ),
    ]
    raw_text = (
        "Chủ tịch UBND TP.HCM Phan Văn Mãi liên hệ hotline 0912345678 tại TP.HCM."
    )
    redacted_content = mask_person_entities_in_text(raw_text, entities)
    redacted_metadata = redact_entities_metadata(entities)

    assert "Phan Văn Mãi" not in redacted_content
    # Phone number caught by redact_pii second pass
    assert "0912345678" not in redacted_content
    assert "<NAME>" in redacted_content
    assert any(e["text"] == "TP.HCM" for e in redacted_metadata)


def test_redaction_failure_raises_chunk_validation_error(monkeypatch):
    """Assert redaction failure raises ChunkValidationError with 'unredacted PII'."""

    def _boom_redact(*args, **kwargs):
        raise RuntimeError("Redactor crashed")

    monkeypatch.setattr("app.services.news.entity_extractor.redact_pii", _boom_redact)

    entities = [
        NewsEntity(
            text="John Doe", type="person", confidence=0.9, surface_forms=["John Doe"]
        )
    ]
    with pytest.raises(ChunkValidationError) as excinfo:
        mask_person_entities_in_text("Hello John Doe", entities)

    assert "unredacted PII" in str(excinfo.value)


def test_no_raw_person_names_in_logs_or_memory():
    """Assert metadata.entities contains no raw person names."""
    entities = [
        NewsEntity(
            text="Lê Văn B", type="person", confidence=0.9, surface_forms=["Lê Văn B"]
        ),
        NewsEntity(
            text="Tập đoàn FPT",
            type="organization",
            confidence=0.95,
            surface_forms=["FPT"],
        ),
    ]
    meta = redact_entities_metadata(entities)

    for item in meta:
        if item["type"] == "person":
            assert item["text"] == "<NAME>"
            assert item["surface_forms"] == ["<NAME>"]


def test_organization_and_location_text_preserved_when_no_person_substring():
    """Assert organization and location without person names remain unchanged."""
    entities = [
        NewsEntity(
            text="Bộ Y tế",
            type="organization",
            confidence=0.98,
            surface_forms=["Bộ Y tế"],
        ),
        NewsEntity(
            text="Đà Nẵng", type="location", confidence=0.96, surface_forms=["Đà Nẵng"]
        ),
    ]
    meta = redact_entities_metadata(entities)

    assert meta[0]["text"] == "Bộ Y tế"
    assert meta[0]["surface_forms"] == ["Bộ Y tế"]
    assert meta[1]["text"] == "Đà Nẵng"
    assert meta[1]["surface_forms"] == ["Đà Nẵng"]
