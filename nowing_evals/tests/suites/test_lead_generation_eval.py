"""Unit and regression tests for Lead Generation evaluation metrics, gate checks, and runner."""

from __future__ import annotations

import pytest

from nowing_evals.core.registry import RunContext, get, list_benchmarks
from nowing_evals.suites.lead_generation.metrics import (
    _match_lead_entity,
    _normalize_identifier,
    _strip_vietnamese_accents,
    contact_accuracy,
    duplicate_rate,
    false_positive_rate,
    icp_match_rate,
    intent_signal_precision,
    precision_at_k,
    recall_at_source,
    time_to_first_lead,
)
from nowing_evals.suites.lead_generation.runner import (
    LeadGenerationBenchmark,
    evaluate_lead_generation_gate,
    load_lead_generation_gate,
)


class TestLeadGenerationMetrics:
    """Test 8 enterprise lead generation evaluation metrics."""

    def test_strip_vietnamese_accents_and_normalize(self):
        """Accent stripping and phone/tax ID normalization work as expected."""
        assert _strip_vietnamese_accents("Công Ty Cổ Phần Công Nghệ") == "cong ty co phan cong nghe"
        assert _strip_vietnamese_accents("Đà Nẵng") == "da nang"
        assert _normalize_identifier("+84 908-123.456") == "84908123456"
        assert _normalize_identifier("0312.345.678") == "0312345678"

    def test_match_lead_entity_by_tax_id(self):
        """Lead matching succeeds on identical normalized Tax ID."""
        lead = {"tax_id": "0312-345-678", "name": "A"}
        gt = {"tax_id": "0312345678", "name": "B"}
        assert _match_lead_entity(lead, gt) is True

    def test_match_lead_entity_by_canonical_domain(self):
        """Lead matching succeeds on canonical domain."""
        lead = {"domain": "tiki.vn", "company_name": "Tiki Corp"}
        gt = {"canonical_domain": "tiki.vn", "company_name": "Công ty Tiki"}
        assert _match_lead_entity(lead, gt) is True

    def test_match_lead_entity_by_phone(self):
        """Lead matching succeeds on phone number match."""
        lead = {"phone": "+84 908 123 456"}
        gt = {"primary_phone": "84908123456"}
        assert _match_lead_entity(lead, gt) is True

    def test_match_lead_entity_by_name_fuzzy(self):
        """Lead matching succeeds on Vietnamese company name overlap without accents."""
        lead = {"company_name": "Cong ty FPT Software"}
        gt = {"name": "Công ty Cổ phần FPT Software"}
        assert _match_lead_entity(lead, gt) is True

    def test_precision_at_k(self):
        """Precision@k returns correct fraction of valid retrieved entities."""
        gt = [{"tax_id": "0101"}, {"tax_id": "0102"}, {"tax_id": "0103"}]
        retrieved = [{"tax_id": "0101"}, {"tax_id": "0102"}, {"tax_id": "9999"}]

        assert precision_at_k(retrieved, gt, k=2) == 1.0
        assert precision_at_k(retrieved, gt, k=3) == round(2 / 3, 4)
        assert precision_at_k([], gt) == 0.0
        assert precision_at_k(retrieved, []) == 0.0
        assert precision_at_k([], []) == 1.0

    def test_recall_at_source(self):
        """Recall@Source calculates fraction of resolved scraper sources."""
        expected = ["masothue", "linkedin", "thongtindoanhnghiep"]
        discovered = ["masothue", "linkedin", "facebook_groups"]
        assert recall_at_source(discovered, expected) == round(2 / 3, 4)
        assert recall_at_source([], expected) == 0.0
        assert recall_at_source(discovered, []) == 1.0

    def test_icp_match_rate(self):
        """ICP Match Rate validates firmographic constraints (scalars, ranges, lists)."""
        criteria = {
            "industry": "Công nghệ thông tin",
            "company_size": {"min": 50, "max": 200},
            "location": "Hà Nội",
        }
        valid_lead = {
            "industry": "Công nghệ thông tin và Truyền thông",
            "company_size": 100,
            "location": "Thành phố Hà Nội",
        }
        invalid_lead_size = {
            "industry": "Công nghệ thông tin",
            "company_size": 10,
            "location": "Hà Nội",
        }
        invalid_lead_loc = {
            "industry": "Công nghệ thông tin",
            "company_size": 120,
            "location": "TP. Hồ Chí Minh",
        }

        leads = [valid_lead, invalid_lead_size, invalid_lead_loc]
        assert icp_match_rate(leads, criteria) == round(1 / 3, 4)
        assert icp_match_rate([valid_lead], criteria) == 1.0
        assert icp_match_rate([], criteria) == 0.0
        assert icp_match_rate(leads, {}) == 1.0

    def test_intent_signal_precision(self):
        """Intent signal precision evaluates matching buying/hiring signals."""
        expected = ["tuyển dụng IT", "mở rộng chi nhánh"]
        leads = [
            {"intent": "Đang tuyển dụng IT gấp"},
            {"intent_signal": "Mở rộng chi nhánh mới tại Đà Nẵng"},
            {"intent": "Không có nhu cầu"},
        ]
        assert intent_signal_precision(leads, expected) == round(2 / 3, 4)
        assert intent_signal_precision([], expected) == 0.0
        assert intent_signal_precision(leads, []) == 1.0

    def test_contact_accuracy(self):
        """Contact accuracy verifies phone, email, or active zalo reachability."""
        leads = [
            {"phone": "0908123456", "email": "contact@abc.vn"},
            {"phone": "invalid_phone", "email": "info@corp.com"},
            {"phone": "0389123456", "email": "bad-email"},
            {"phone": "123", "email": "invalid"},
        ]
        # Leads 0, 1, 2 have at least one valid contact channel
        assert contact_accuracy(leads) == 0.75
        assert contact_accuracy([]) == 0.0

    def test_duplicate_rate(self):
        """Duplicate rate calculates ratio of redundant candidate leads."""
        assert duplicate_rate(100, 70) == 0.30
        assert duplicate_rate(100, 100) == 0.0
        assert duplicate_rate(0, 0) == 0.0
        assert duplicate_rate(50, 60) == 0.0

    def test_false_positive_rate(self):
        """False positive rate measures proportion of distractors returned."""
        negatives = [
            {"tax_id": "9001", "name": "Disqualified 1"},
            {"tax_id": "9002", "name": "Disqualified 2"},
        ]
        retrieved = [
            {"tax_id": "0101", "name": "Valid Corp"},
            {"tax_id": "9001", "name": "Disqualified 1"},
        ]
        assert false_positive_rate(retrieved, negatives) == 0.5
        assert false_positive_rate(retrieved, []) == 0.0
        assert false_positive_rate([], negatives) == 0.0

    def test_time_to_first_lead(self):
        """Time to first lead aggregates latency observations."""
        assert time_to_first_lead(350.5) == 350.5
        assert time_to_first_lead([200.0, 300.0, 400.0]) == 300.0
        assert time_to_first_lead([]) == 0.0


class TestLeadGenerationGate:
    """Test gate validation against thresholds."""

    def test_gate_evaluation_passes(self):
        """Gate passes when all 8 metrics meet enterprise thresholds."""
        metrics = {
            "precision_at_k": 0.90,
            "recall_at_source": 0.88,
            "icp_match_rate": 0.92,
            "intent_signal_precision": 0.85,
            "contact_accuracy": 0.95,
            "duplicate_rate": 0.15,
            "false_positive_rate": 0.02,
            "time_to_first_lead_ms": 320.0,
            "total_cases": 50,
        }
        thresholds = {
            "min_precision_at_k": 0.85,
            "min_recall_at_source": 0.80,
            "min_icp_match_rate": 0.85,
            "min_intent_signal_precision": 0.80,
            "min_contact_accuracy": 0.85,
            "max_duplicate_rate": 0.40,
            "max_false_positive_rate": 0.05,
            "max_time_to_first_lead_ms": 2000.0,
            "min_cases": 50,
        }
        passed, reasons = evaluate_lead_generation_gate(metrics, thresholds)
        assert passed is True
        assert reasons == []

    def test_gate_evaluation_fails_on_metrics(self):
        """Gate fails if precision or false positive rate violate bounds."""
        metrics = {
            "precision_at_k": 0.70,  # Below 0.85
            "recall_at_source": 0.88,
            "icp_match_rate": 0.92,
            "intent_signal_precision": 0.85,
            "contact_accuracy": 0.95,
            "duplicate_rate": 0.15,
            "false_positive_rate": 0.08,  # Above 0.05
            "time_to_first_lead_ms": 320.0,
            "total_cases": 50,
        }
        thresholds = {
            "min_precision_at_k": 0.85,
            "min_recall_at_source": 0.80,
            "min_icp_match_rate": 0.85,
            "min_intent_signal_precision": 0.80,
            "min_contact_accuracy": 0.85,
            "max_duplicate_rate": 0.40,
            "max_false_positive_rate": 0.05,
            "max_time_to_first_lead_ms": 2000.0,
            "min_cases": 50,
        }
        passed, reasons = evaluate_lead_generation_gate(metrics, thresholds)
        assert passed is False
        assert len(reasons) == 2
        assert any("precision_at_k" in r for r in reasons)
        assert any("false_positive_rate" in r for r in reasons)


class TestLeadGenerationBenchmarkRunner:
    """Test runner execution, suite discovery, and reporting."""

    def test_suite_registered_and_discoverable(self):
        """Lead generation benchmark is registered in the core registry."""
        benchmarks = list_benchmarks()
        keys = {(b.suite, b.name) for b in benchmarks}
        assert ("lead_generation", "regression") in keys

        bench = get("lead_generation", "regression")
        assert bench is not None
        assert isinstance(bench, LeadGenerationBenchmark)

    def test_golden_dataset_contains_at_least_50_cases_and_5_verticals(self):
        """Packaged golden dataset satisfies enterprise coverage requirements."""
        bench = LeadGenerationBenchmark()
        cases = bench._load_golden_cases()
        assert len(cases) >= 50

        verticals = {c["vertical"] for c in cases}
        expected_verticals = {"saas", "real_estate", "recruitment", "procurement", "ecommerce"}
        assert expected_verticals.issubset(verticals)

    @pytest.mark.asyncio
    async def test_full_benchmark_run_end_to_end(self, tmp_path):
        """Benchmark runs end-to-end and produces verified pass artifact."""
        import httpx

        from nowing_evals.core.config import Config

        cfg = Config(
            nowing_api_base="http://localhost:8000",
            openrouter_api_key=None,
            openrouter_base_url="https://openrouter.ai/api/v1",
            nowing_jwt="test-jwt",
            nowing_refresh_token=None,
            nowing_user_email=None,
            nowing_user_password=None,
            data_dir=tmp_path / "data",
            reports_dir=tmp_path / "reports",
        )

        ctx = RunContext(
            suite="lead_generation",
            benchmark="regression",
            config=cfg,
            suite_state=None,  # type: ignore[arg-type]
            http=httpx.AsyncClient(),
            mode="replay",
        )

        bench = LeadGenerationBenchmark()
        artifact = await bench.run(ctx)

        assert artifact.suite == "lead_generation"
        assert artifact.benchmark == "regression"
        assert artifact.metrics["total_cases"] >= 50
        assert artifact.metrics["precision_at_k"] >= 0.85
        assert artifact.metrics["recall_at_source"] >= 0.80
        assert artifact.metrics["icp_match_rate"] >= 0.85
        assert artifact.metrics["intent_signal_precision"] >= 0.80
        assert artifact.metrics["contact_accuracy"] >= 0.85
        assert artifact.metrics["duplicate_rate"] <= 0.40
        assert artifact.metrics["false_positive_rate"] <= 0.05
        assert artifact.extra["gate"]["passed"] is True

        # Test report section formatting
        section = bench.report_section([artifact])
        assert "Lead Generation Enterprise Benchmark" in section.title
        assert "AI Lead Generation Enterprise Benchmark" in section.body_md
        assert "PASSED" in section.body_md
        assert "| `saas` |" in section.body_md
        assert "| `real_estate` |" in section.body_md
