"""Unit tests for Narrative Report Engine and synthesis logic (Story 6.12)."""

from __future__ import annotations

from app.reports.narrative.engine import NarrativeSynthesisEngine
from app.reports.narrative.models import SourceCitation
from app.reports.narrative.registry import NarrativeTemplateRegistry


def test_registry_initializes_three_canonical_templates() -> None:
    """Registry should contain news_digest, financial_trend, company_timeline (AC-1)."""
    templates = NarrativeTemplateRegistry.list_all()
    template_ids = {t.template_id for t in templates}

    assert "news_digest" in template_ids
    assert "financial_trend" in template_ids
    assert "company_timeline" in template_ids


def test_news_digest_synthesis_structure_and_citations() -> None:
    """News digest synthesis should format Executive Summary, stories, sentiment and citations."""
    tmpl = NarrativeTemplateRegistry.get("news_digest")
    assert tmpl is not None

    items = [
        {"title": "VinFast EV Delivery Surge", "summary": "Deliveries grew 40% in Q2", "id": "news-101"},
        {"title": "Battery Plant Expansion", "summary": "New facility breaks ground", "id": "news-102"},
    ]
    citations = [
        SourceCitation(source_id="news-101", title="VinFast EV Delivery Surge", url="https://news.vn/101"),
        SourceCitation(source_id="news-102", title="Battery Plant Expansion", url="https://news.vn/102"),
    ]

    content = NarrativeSynthesisEngine.synthesize_narrative(
        template=tmpl,
        parameters={"topic": "VinFast"},
        items=items,
        degraded=False,
        reasons=[],
        citations=citations,
    )

    assert "Executive News Digest: VinFast" in content
    assert "VinFast EV Delivery Surge" in content
    assert "[news-101]" in content
    assert "Danh mục Trích dẫn & Nguồn Tham chiếu" in content
    assert "https://news.vn/101" in content


def test_financial_trend_synthesis_structure() -> None:
    """Financial trend report outputs margin, growth, and leverage sections."""
    tmpl = NarrativeTemplateRegistry.get("financial_trend")
    assert tmpl is not None

    items = [
        {"period": "2026-Q1", "revenue": 15000, "profit": 2500, "id": "fin-1"},
    ]
    citations = [
        SourceCitation(source_id="fin-1", title="CafeF VNM Q1 Financials", url="https://cafef.vn/VNM"),
    ]

    content = NarrativeSynthesisEngine.synthesize_narrative(
        template=tmpl,
        parameters={"symbol": "VNM"},
        items=items,
        degraded=False,
        reasons=[],
        citations=citations,
    )

    assert "Báo cáo Xu hướng Tài chính: VNM" in content
    assert "Doanh thu & Biên Lợi nhuận" in content
    assert "[fin-1]" in content


def test_company_timeline_synthesis_structure() -> None:
    """Company timeline formats events chronologically with date badges."""
    tmpl = NarrativeTemplateRegistry.get("company_timeline")
    assert tmpl is not None

    items = [
        {"date": "2026-05-10", "title": "Thay đổi vốn điều lệ lên 500 tỷ", "id": "mst-1"},
        {"date": "2026-08-01", "title": "Bổ nhiệm Tổng Giám đốc mới", "id": "mst-2"},
    ]
    citations = [
        SourceCitation(source_id="mst-1", title="Mã Số Thuế FPT Profile", url="https://masothue.com/0101248141"),
        SourceCitation(source_id="mst-2", title="Mã Số Thuế FPT Profile", url="https://masothue.com/0101248141"),
    ]

    content = NarrativeSynthesisEngine.synthesize_narrative(
        template=tmpl,
        parameters={"company_name_or_tax_code": "0101248141"},
        items=items,
        degraded=False,
        reasons=[],
        citations=citations,
    )

    assert "Dòng thời gian Pháp lý & Sự kiện: 0101248141" in content
    assert "`[2026-05-10]`" in content
    assert "Thay đổi vốn điều lệ lên 500 tỷ" in content
    assert "[mst-1]" in content


def test_graceful_degradation_on_empty_data() -> None:
    """Empty or failed synthesis returns degraded notice and actionable advice (AC-4)."""
    tmpl = NarrativeTemplateRegistry.get("news_digest")
    assert tmpl is not None

    content = NarrativeSynthesisEngine.synthesize_narrative(
        template=tmpl,
        parameters={"topic": "Unknown Topic"},
        items=[],
        degraded=True,
        reasons=["empty_dataset", "upstream_timeout"],
        citations=[],
    )

    assert "Degraded Report" in content
    assert "empty_dataset" in content
    assert "upstream_timeout" in content
    assert "Actionable Advice" in content
    assert "Retry Generation" in content
