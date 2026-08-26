"""Red-phase unit tests for Story 25.5 — scraper rule validator.

These tests encode the expected contract and will fail until
`app/services/scraper_rule_validator.py` is implemented.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest

pytestmark = [pytest.mark.unit]


def _load_validator() -> Any:
    """Lazy loader so the test module can be collected before the source exists."""
    try:
        return importlib.import_module("app.services.scraper_rule_validator")
    except ModuleNotFoundError as exc:
        pytest.fail(f"not implemented: {exc}")


def _load_rule_schema() -> Any:
    """Lazy loader for the Pydantic RuleSchema model."""
    try:
        return importlib.import_module("app.schemas.admin_scraper_rules")
    except ModuleNotFoundError as exc:
        pytest.fail(f"not implemented: {exc}")


class TestValidateCssSelectors:
    """AC-2 / AC-3: CSS selector syntax validation."""

    def test_valid_selectors_parse(self) -> None:
        mod = _load_validator()
        result = mod.validate_css_selectors(
            {
                "listing_card": "div.js__card-listing",
                "title": "span.js__card-title",
                "next_page_link": "a.next",
            }
        )
        assert result is True or result == {}

    def test_invalid_selector_raises_invalid_css(self) -> None:
        mod = _load_validator()
        with pytest.raises(mod.InvalidSelectorError) as exc:
            mod.validate_css_selectors({"title": "span["})
        assert "Invalid CSS selector" in str(exc.value)

    def test_empty_selectors_is_allowed(self) -> None:
        mod = _load_validator()
        assert mod.validate_css_selectors({}) is True


class TestValidateRegexes:
    """AC-2 / AC-3: ReDoS-safe regex validation."""

    def test_safe_regex_compiles(self) -> None:
        mod = _load_validator()
        result = mod.validate_regexes({"phone": r"\d{10,15}"})
        assert result is True or result == {}

    def test_redos_pattern_raises_timeout(self) -> None:
        mod = _load_validator()
        with pytest.raises(mod.ReDoSTimeoutError) as exc:
            mod.validate_regexes({"dangerous": r"(a+)+$"})
        assert "REDOS_TIMEOUT" in str(exc.value)

    def test_redos_pattern_with_classic_input(self) -> None:
        mod = _load_validator()
        with pytest.raises(mod.ReDoSTimeoutError):
            mod.benchmark_redos(r"(a+)+$", "a" * 30 + "!")

    def test_redos_pattern_with_alternation_input(self) -> None:
        mod = _load_validator()
        with pytest.raises(mod.ReDoSTimeoutError):
            mod.benchmark_redos(r"(a|aa)+$", "a" * 30 + "!")

    def test_benchmark_returns_max_ms_for_safe_pattern(self) -> None:
        mod = _load_validator()
        max_ms = mod.benchmark_redos(r"\d+", "123456789" * 100)
        assert max_ms < 50.0

    def test_lookbehind_lookahead_rejected_with_google_re2(self) -> None:
        mod = _load_validator()
        with pytest.raises(mod.InvalidRegexError):
            mod.validate_regexes({"phone": r"(?<=\s)\d+(?=\s)"})


class TestRuleSchemaValidation:
    """AC-2: numeric ranges and Pydantic strict validation."""

    def test_valid_rule_schema_parses(self) -> None:
        schemas = _load_rule_schema()
        rule = schemas.RuleSchema(
            selectors={"title": "span.js__card-title"},
            regexes={"phone": r"\d{10,15}"},
            delays={"request_ms": 1500, "retry_base_ms": 1000},
            retries={"max_attempts": 3, "statuses": [429, 500]},
            circuit_breaker={
                "error_threshold_pct": 20,
                "min_calls": 10,
                "trip_duration_seconds": 300,
                "tripped": False,
            },
        )
        assert rule.delays.request_ms == 1500

    def test_request_ms_boundary_60000_accepted(self) -> None:
        schemas = _load_rule_schema()
        rule = schemas.RuleSchema(
            delays={"request_ms": 60000, "retry_base_ms": 0},
            retries={"max_attempts": 0, "statuses": []},
            circuit_breaker={
                "error_threshold_pct": 0,
                "min_calls": 0,
                "trip_duration_seconds": 1,
                "tripped": False,
            },
        )
        assert rule.delays.request_ms == 60000

    def test_request_ms_above_max_rejected(self) -> None:
        schemas = _load_rule_schema()
        with pytest.raises(ValueError):
            schemas.RuleSchema(
                delays={"request_ms": 60001, "retry_base_ms": 1000},
                retries={"max_attempts": 3, "statuses": [500]},
                circuit_breaker={
                    "error_threshold_pct": 20,
                    "min_calls": 10,
                    "trip_duration_seconds": 300,
                    "tripped": False,
                },
            )

    def test_extra_fields_forbidden(self) -> None:
        schemas = _load_rule_schema()
        with pytest.raises(ValueError):
            schemas.RuleSchema(
                selectors={},
                extra_field="should not be allowed",
            )

    def test_negative_numeric_rejected(self) -> None:
        schemas = _load_rule_schema()
        with pytest.raises(ValueError):
            schemas.RuleSchema(
                delays={"request_ms": -1, "retry_base_ms": 1000},
                retries={"max_attempts": 3, "statuses": [500]},
                circuit_breaker={
                    "error_threshold_pct": 20,
                    "min_calls": 10,
                    "trip_duration_seconds": 300,
                    "tripped": False,
                },
            )

    def test_error_threshold_pct_boundary_100_accepted(self) -> None:
        schemas = _load_rule_schema()
        rule = schemas.RuleSchema(
            circuit_breaker={
                "error_threshold_pct": 100,
                "min_calls": 1,
                "trip_duration_seconds": 1,
                "tripped": False,
            },
        )
        assert rule.circuit_breaker.error_threshold_pct == 100

    def test_max_attempts_above_10_rejected(self) -> None:
        schemas = _load_rule_schema()
        with pytest.raises(ValueError):
            schemas.RuleSchema(
                retries={"max_attempts": 11, "statuses": [500]},
            )


class TestValidationDoesNotBlockEventLoop:
    """AC-3: sandbox must run off the main event loop."""

    async def test_benchmark_runs_in_thread(self) -> None:
        mod = _load_validator()
        # The implementation should raise ReDoSTimeoutError from a background thread.
        with pytest.raises(mod.ReDoSTimeoutError):
            await mod.validate_regexes_async({"dangerous": r"(a+)+$"})
