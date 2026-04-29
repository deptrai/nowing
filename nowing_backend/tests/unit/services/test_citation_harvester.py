"""Unit tests for app.services.citation_harvester.

Covers:
- _infer_provider: provider detection from citation ID suffix/prefix/infix
- harvest_citations: tag extraction, deduplication, output shape
- strip_cite_tags: tag removal preserving inner text
"""

from __future__ import annotations

import pytest

from app.services.citation_harvester import (
    _infer_provider,
    harvest_citations,
    strip_cite_tags,
)


# ---------------------------------------------------------------------------
# _infer_provider
# ---------------------------------------------------------------------------


class TestInferProvider:
    @pytest.mark.parametrize(
        "cite_id, expected",
        [
            ("price-current-coingecko", "CoinGecko"),
            ("tvl-total-defillama", "DefiLlama"),
            ("security-score-goplus", "GoPlus"),
            ("contract-info-etherscan", "Etherscan"),
            ("pair-price-dexscreener", "DexScreener"),
            ("metrics-messari", "Messari"),
            ("market-cap-coinmarketcap", "CoinMarketCap"),
        ],
    )
    def test_suffix_match(self, cite_id: str, expected: str):
        assert _infer_provider(cite_id) == expected

    @pytest.mark.parametrize(
        "cite_id, expected",
        [
            ("coingecko-price-btc", "CoinGecko"),
            ("defillama-tvl-overview", "DefiLlama"),
            ("goplus-security-1", "GoPlus"),
        ],
    )
    def test_prefix_match(self, cite_id: str, expected: str):
        assert _infer_provider(cite_id) == expected

    @pytest.mark.parametrize(
        "cite_id, expected",
        [
            ("data-coingecko-price", "CoinGecko"),
            ("live-defillama-tvl", "DefiLlama"),
        ],
    )
    def test_infix_match(self, cite_id: str, expected: str):
        assert _infer_provider(cite_id) == expected

    def test_unknown_provider(self):
        assert _infer_provider("unknown-source-42") == "Unknown"

    def test_case_insensitive(self):
        assert _infer_provider("price-COINGECKO") == "CoinGecko"
        assert _infer_provider("TVL-DEFILLAMA") == "DefiLlama"

    def test_empty_string(self):
        assert _infer_provider("") == "Unknown"

    def test_no_separator(self):
        assert _infer_provider("coingecko") == "Unknown"


# ---------------------------------------------------------------------------
# harvest_citations
# ---------------------------------------------------------------------------


class TestHarvestCitations:
    def test_single_citation(self):
        text = "Price is [[cite:price-coingecko]]$2.34[[/cite]] today."
        result = harvest_citations(text)
        assert "price-coingecko" in result
        entry = result["price-coingecko"]
        assert entry["id"] == "price-coingecko"
        assert entry["value"] == "$2.34"
        assert entry["sources"][0]["provider"] == "CoinGecko"
        assert entry["sources"][0]["rawValue"] == "$2.34"
        assert "fetchedAt" in entry["sources"][0]

    def test_multiple_citations(self):
        text = (
            "TVL is [[cite:tvl-defillama]]$1.5B[[/cite]] "
            "and price is [[cite:price-coingecko]]$2.34[[/cite]]."
        )
        result = harvest_citations(text)
        assert len(result) == 2
        assert "tvl-defillama" in result
        assert "price-coingecko" in result

    def test_duplicate_id_first_wins(self):
        text = (
            "[[cite:price-coingecko]]$2.34[[/cite]] "
            "later [[cite:price-coingecko]]$2.50[[/cite]]"
        )
        result = harvest_citations(text)
        assert len(result) == 1
        assert result["price-coingecko"]["value"] == "$2.34"

    def test_no_citations(self):
        result = harvest_citations("Just plain text, no citations here.")
        assert result == {}

    def test_empty_input(self):
        result = harvest_citations("")
        assert result == {}

    def test_multiline_value(self):
        text = "[[cite:data-defillama]]line1\nline2[[/cite]]"
        result = harvest_citations(text)
        assert result["data-defillama"]["value"] == "line1\nline2"

    def test_whitespace_in_id_stripped(self):
        text = "[[cite: price-coingecko ]]$2.34[[/cite]]"
        result = harvest_citations(text)
        assert "price-coingecko" in result

    def test_adjacent_citations(self):
        text = "[[cite:a-coingecko]]1[[/cite]][[cite:b-defillama]]2[[/cite]]"
        result = harvest_citations(text)
        assert len(result) == 2

    def test_output_shape(self):
        text = "[[cite:sec-goplus]]safe[[/cite]]"
        result = harvest_citations(text)
        entry = result["sec-goplus"]
        assert set(entry.keys()) == {"id", "value", "sources"}
        src = entry["sources"][0]
        assert set(src.keys()) == {"provider", "fetchedAt", "rawValue"}

    def test_unknown_provider_in_output(self):
        text = "[[cite:custom-xyz]]value[[/cite]]"
        result = harvest_citations(text)
        assert result["custom-xyz"]["sources"][0]["provider"] == "Unknown"


# ---------------------------------------------------------------------------
# strip_cite_tags
# ---------------------------------------------------------------------------


class TestStripCiteTags:
    def test_removes_tags_keeps_value(self):
        text = "Price is [[cite:p-coingecko]]$2.34[[/cite]] today."
        assert strip_cite_tags(text) == "Price is $2.34 today."

    def test_multiple_tags(self):
        text = "[[cite:a]]1[[/cite]] and [[cite:b]]2[[/cite]]"
        assert strip_cite_tags(text) == "1 and 2"

    def test_no_tags_returns_original(self):
        text = "Just plain text."
        assert strip_cite_tags(text) == text

    def test_empty_input(self):
        assert strip_cite_tags("") == ""

    def test_multiline_content(self):
        text = "[[cite:x]]line1\nline2[[/cite]]"
        assert strip_cite_tags(text) == "line1\nline2"

    def test_nested_brackets_in_value(self):
        text = "[[cite:y]]value [with] brackets[[/cite]]"
        assert strip_cite_tags(text) == "value [with] brackets"
