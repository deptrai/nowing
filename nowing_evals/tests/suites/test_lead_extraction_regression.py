"""Unit and integration tests for lead extraction regression metrics and runner."""

from __future__ import annotations

import pytest
import respx
from httpx import Response


class TestLeadExtractionMetrics:
    """Test F1 phone, hallucination rate, MST modulo 11, and company name metrics."""

    def test_f1_phone_calculation_exact_match(self):
        """Exact match between predicted and expected phone sets yields F1 = 1.0."""
        from nowing_evals.suites.lead_extraction.regression.metrics import f1_phone

        predicted = {"0908123456", "0912345678"}
        expected = {"0908123456", "0912345678"}
        assert f1_phone(predicted, expected) == 1.0

    def test_f1_phone_calculation_partial_match(self):
        """Partial match computes correct precision, recall, and harmonic mean."""
        from nowing_evals.suites.lead_extraction.regression.metrics import f1_phone

        predicted = {"0908123456", "0999999999"}
        expected = {"0908123456", "0912345678"}
        # Precision = 1/2, Recall = 1/2 -> F1 = 0.5
        assert f1_phone(predicted, expected) == 0.5

    def test_hallucination_rate_zero_when_all_in_source(self):
        """Zero hallucination rate when all predicted entities exist in ground truth or source text."""
        from nowing_evals.suites.lead_extraction.regression.metrics import hallucination_rate

        predicted_phones = {"0908123456"}
        predicted_tax_ids = {"0100109106"}
        source_text = "Liên hệ 0908123456 MST 0100109106"
        expected_phones = {"0908123456"}
        expected_tax_ids = {"0100109106"}

        rate = hallucination_rate(
            predicted_phones, predicted_tax_ids, source_text, expected_phones, expected_tax_ids
        )
        assert rate == 0.0

    def test_hallucination_rate_ignores_plus_84_and_obfuscation(self):
        """+84, 84, and obfuscated phones in source text are not treated as hallucinations."""
        from nowing_evals.suites.lead_extraction.regression.metrics import hallucination_rate

        rate = hallucination_rate(
            predicted_phones={"0987654321", "0908889999", "0798889999", "0912345678"},
            predicted_tax_ids=set(),
            source_text="Alo ngay +84 987 654 321, SĐT Zalo 84908889999, gọi o79-888-9999, hoặc O912.345.678",
            expected_phones=set(),
            expected_tax_ids=set(),
        )
        assert rate == 0.0

    def test_hallucination_rate_none_source_is_safe(self):
        """A None source text is handled without crashing."""
        from nowing_evals.suites.lead_extraction.regression.metrics import hallucination_rate

        rate = hallucination_rate(
            predicted_phones={"0908123456"},
            predicted_tax_ids=set(),
            source_text=None,
            expected_phones=set(),
            expected_tax_ids=set(),
        )
        assert rate == 1.0

    def test_mst_modulo11_accuracy_calculation(self):
        """Calculates fraction of valid tax codes from boolean results."""
        from nowing_evals.suites.lead_extraction.regression.metrics import mst_modulo11_accuracy

        assert mst_modulo11_accuracy([True, True, True, True]) == 1.0
        assert mst_modulo11_accuracy([True, False]) == 0.5
        assert mst_modulo11_accuracy([]) == 1.0

    def test_company_name_f1_exact_match(self):
        """Token-level F1 returns 1.0 for matching company names."""
        from nowing_evals.suites.lead_extraction.regression.metrics import company_name_f1

        assert company_name_f1("Công ty TNHH ABC", "Công ty TNHH ABC") == 1.0
        assert company_name_f1("  Công ty TNHH ABC  ", "Công ty TNHH ABC") == 1.0

    def test_company_name_f1_empty_both(self):
        """Both missing company names score 1.0; one missing scores 0.0."""
        from nowing_evals.suites.lead_extraction.regression.metrics import company_name_f1

        assert company_name_f1(None, None) == 1.0
        assert company_name_f1("", "") == 1.0
        assert company_name_f1("Công ty", None) == 0.0


class TestLeadExtractionGateEvaluation:
    """Test benchmark-local gate evaluation against thresholds."""

    def test_gate_evaluation_passes_when_above_thresholds(self):
        """Gate passes when F1 >= 0.98, Hallucination <= 0.001, MST >= 0.995."""
        from nowing_evals.suites.lead_extraction.regression.runner import (
            evaluate_lead_extraction_gate,
        )

        metrics = {
            "f1_phone": 0.99,
            "hallucination_rate": 0.0005,
            "mst_modulo11_accuracy": 1.0,
            "total_cases": 20,
        }
        thresholds = {
            "min_f1_phone": 0.98,
            "max_hallucination_rate": 0.001,
            "min_mst_modulo11_accuracy": 0.995,
            "min_cases": 10,
        }
        passed, reasons = evaluate_lead_extraction_gate(metrics, thresholds)
        assert passed is True
        assert reasons == []

    def test_gate_evaluation_fails_when_below_threshold(self):
        """Gate fails with specific reason when F1 falls below target."""
        from nowing_evals.suites.lead_extraction.regression.runner import (
            evaluate_lead_extraction_gate,
        )

        metrics = {
            "f1_phone": 0.95,
            "hallucination_rate": 0.0,
            "mst_modulo11_accuracy": 1.0,
            "total_cases": 20,
        }
        thresholds = {
            "min_f1_phone": 0.98,
            "max_hallucination_rate": 0.001,
            "min_mst_modulo11_accuracy": 0.995,
            "min_cases": 10,
        }
        passed, reasons = evaluate_lead_extraction_gate(metrics, thresholds)
        assert passed is False
        assert any("min_f1_phone" in r for r in reasons)

    def test_gate_evaluation_fails_when_metrics_missing(self):
        """Missing primary metrics are treated as gate failures."""
        from nowing_evals.suites.lead_extraction.regression.runner import (
            evaluate_lead_extraction_gate,
        )

        passed, reasons = evaluate_lead_extraction_gate({"f1_phone": 0.99}, {})
        assert passed is False
        assert any("missing" in r for r in reasons)


class TestExtractorClientReplay:
    """Test replay-mode ExtractorClient and cassette path traversal defences."""

    def test_replay_returns_cassette_body(self, tmp_path):
        """ExtractorClient in replay mode returns the cassette body and makes no HTTP call."""
        import httpx

        from nowing_evals.core.cassette import Cassette
        from nowing_evals.core.registry import RunContext
        from nowing_evals.suites.lead_extraction.regression.extractor_client import (
            ExtractorClient,
        )

        cassette_path = tmp_path / "lead-001.sse.jsonl"
        Cassette(
            type="rest",
            status=200,
            body={
                "phones": ["0908123456"],
                "tax_ids": ["0100109106"],
                "tax_ids_valid": [True],
                "company_name": "Công ty TNHH ABC",
            },
        ).save(cassette_path)

        ctx = RunContext(
            suite="lead_extraction",
            benchmark="regression",
            config=None,  # type: ignore[arg-type]
            suite_state=None,  # type: ignore[arg-type]
            http=httpx.AsyncClient(),
            mode="replay",
        )
        # cassettes_dir is normally inside data; we override via the cassette path parent.
        ctx.replay_artifacts_dir = lambda: tmp_path  # type: ignore[method-assign]

        client = ExtractorClient(ctx)

        result = None

        async def _run() -> None:
            nonlocal result
            result = await client.extract_entities("lead-001", "unused")

        import asyncio

        asyncio.run(_run())

        assert result == {
            "phones": ["0908123456"],
            "tax_ids": ["0100109106"],
            "tax_ids_valid": [True],
            "company_name": "Công ty TNHH ABC",
        }

    def test_replay_missing_cassette_fails_closed(self, tmp_path):
        """Missing cassette in replay mode raises FileNotFoundError."""
        import httpx

        from nowing_evals.core.registry import RunContext
        from nowing_evals.suites.lead_extraction.regression.extractor_client import (
            ExtractorClient,
        )

        ctx = RunContext(
            suite="lead_extraction",
            benchmark="regression",
            config=None,  # type: ignore[arg-type]
            suite_state=None,  # type: ignore[arg-type]
            http=httpx.AsyncClient(),
            mode="replay",
        )
        ctx.replay_artifacts_dir = lambda: tmp_path  # type: ignore[method-assign]

        client = ExtractorClient(ctx)

        with pytest.raises(FileNotFoundError):
            import asyncio

            asyncio.run(client.extract_entities("missing-case", "unused"))

    def test_replay_case_id_path_traversal_rejected(self, tmp_path):
        """case_id containing path separators is rejected before filesystem access."""
        import httpx

        from nowing_evals.core.registry import RunContext
        from nowing_evals.suites.lead_extraction.regression.extractor_client import (
            ExtractorClient,
        )

        ctx = RunContext(
            suite="lead_extraction",
            benchmark="regression",
            config=None,  # type: ignore[arg-type]
            suite_state=None,  # type: ignore[arg-type]
            http=httpx.AsyncClient(),
            mode="replay",
        )
        ctx.replay_artifacts_dir = lambda: tmp_path  # type: ignore[method-assign]

        client = ExtractorClient(ctx)

        with pytest.raises(ValueError, match="unsafe characters"):
            import asyncio

            asyncio.run(client.extract_entities("../etc/passwd", "unused"))


class TestExtractorClientLive:
    """Test live-mode ExtractorClient with respx."""

    def test_live_call_records_sanitized_cassette(self, tmp_path, monkeypatch):
        """Live mode calls the test endpoint and records a sanitized cassette when requested."""
        import httpx

        from nowing_evals.core.registry import RunContext
        from nowing_evals.suites.lead_extraction.regression.extractor_client import (
            ExtractorClient,
        )

        monkeypatch.setenv("TEST_EXTRACTION_SECRET", "test-secret")

        with respx.mock(base_url="http://localhost:8000") as rspx:
            route = rspx.post("/api/v1/test/extract-entities").mock(
                return_value=Response(
                    200,
                    json={
                        "phones": ["0908123456"],
                        "tax_ids": ["0100109106"],
                        "tax_ids_valid": [True],
                        "company_name": "Công ty TNHH PII",
                    },
                )
            )

            ctx = RunContext(
                suite="lead_extraction",
                benchmark="regression",
                config=None,  # type: ignore[arg-type]
                suite_state=None,  # type: ignore[arg-type]
                http=httpx.AsyncClient(base_url="http://localhost:8000"),
                mode="live",
                record=True,
            )
            ctx.replay_artifacts_dir = lambda: tmp_path  # type: ignore[method-assign]

            client = ExtractorClient(ctx)

            import asyncio

            result = asyncio.run(client.extract_entities("lead-001", "source text"))

            assert route.called is True
            assert result["phones"] == ["0908123456"]

            cassette_file = tmp_path / "lead-001.sse.jsonl"
            assert cassette_file.is_file()
            import json

            cassette = json.loads(cassette_file.read_text(encoding="utf-8").splitlines()[0])
            assert cassette["body"]["company_name"] == "Công ty TNHH Sanitized 1"
            assert cassette["body"]["phones"] == ["0900000001"]


class TestLeadExtractionRunnerValidation:
    """Test runner-level validation and helpers."""

    def test_validate_case_rejects_unsafe_case_id(self):
        """_validate_case rejects unsafe case_ids."""
        from nowing_evals.suites.lead_extraction.regression.runner import _validate_case

        with pytest.raises(ValueError, match="unsafe characters"):
            _validate_case({"case_id": "../escape", "source_markdown": "x"})

    def test_validate_case_coerces_tags(self):
        """_validate_case coerces string tags to a list."""
        from nowing_evals.suites.lead_extraction.regression.runner import _validate_case

        case = _validate_case(
            {"case_id": "lead-test", "source_markdown": "x", "tags": "a,b, c"}
        )
        assert case["tags"] == ["a", "b", "c"]
