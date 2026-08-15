"""Unit tests for Shopee Vietnam Price Normalizer (Story 17.2 / AD-EC-2)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.proprietary.platforms.shopee.normalizer import (
    SHOPEE_PRICE_SCALE,
    ShopeePriceNormalizer,
    extract_ids_from_url,
    normalize_discount,
    normalize_price,
    normalize_product_url,
    normalize_rating,
)

pytestmark = pytest.mark.unit


class TestShopeePriceScaling:
    """AC-2 & AD-EC-2: Decimal price normalization with scale 100,000 and ROUND_HALF_UP."""

    def test_scale_constant_is_100000(self):
        assert Decimal("100000") == SHOPEE_PRICE_SCALE

    def test_normalize_standard_integer_raw_price(self):
        # 15,000,000,000 -> 150,000.00 VNĐ
        raw = 15000000000
        normalized = normalize_price(raw)
        assert isinstance(normalized, Decimal)
        assert normalized == Decimal("150000.00")

    def test_normalize_raw_price_float_free_precision(self):
        # 259,000,000 -> 2,590.00 VNĐ
        raw = 259000000
        normalized = normalize_price(raw)
        assert normalized == Decimal("2590.00")

    def test_normalize_small_price_with_half_up_rounding(self):
        # 333,333 -> 3.33333 -> rounds to 3.33
        raw = 333333
        normalized = normalize_price(raw)
        assert normalized == Decimal("3.33")

        # 333,400 -> 3.334 -> rounds to 3.33
        assert normalize_price(333400) == Decimal("3.33")

        # 333,500 -> 3.335 -> ROUND_HALF_UP rounds to 3.34
        assert normalize_price(333500) == Decimal("3.34")

        # 333,600 -> 3.336 -> rounds to 3.34
        assert normalize_price(333600) == Decimal("3.34")

        # 199,000 -> 1.99
        assert normalize_price(199000) == Decimal("1.99")

    def test_normalize_string_formatted_raw_price(self):
        assert normalize_price("15000000000") == Decimal("150000.00")
        assert normalize_price("50000000") == Decimal("500.00")

    def test_normalize_zero_and_negative_prices(self):
        assert normalize_price(0) == Decimal("0.00")
        assert normalize_price(-100000) == Decimal("0.00")

    def test_normalize_none_and_invalid_inputs(self):
        assert normalize_price(None) is None
        assert normalize_price("") is None
        assert normalize_price("invalid_number") is None
        assert normalize_price("NaN") is None
        assert normalize_price("Infinity") is None
        assert normalize_price("-Infinity") is None

    def test_class_helper_method(self):
        normalizer = ShopeePriceNormalizer()
        assert normalizer.normalize_price(15000000000) == Decimal("150000.00")


class TestShopeeFieldNormalizations:
    """Normalizations for ratings, discount percentages, and Vietnamese text."""

    def test_normalize_rating_clamped_and_rounded(self):
        assert normalize_rating(4.876) == 4.88
        assert normalize_rating(5.0) == 5.0
        assert normalize_rating(0.0) == 0.0
        assert normalize_rating(-1.0) == 0.0
        assert normalize_rating(6.5) == 5.0
        assert normalize_rating(None) == 0.0
        assert normalize_rating(float("nan")) == 0.0
        assert normalize_rating(float("inf")) == 0.0

    def test_normalize_discount_calculation(self):
        # Current: 150,000, Original: 200,000 -> 25%
        cur = Decimal("150000.00")
        orig = Decimal("200000.00")
        assert normalize_discount(cur, orig) == 25

        # With raw discount provided
        assert normalize_discount(cur, orig, raw_discount=30) == 30
        assert normalize_discount(cur, orig, raw_discount="25%") == 25
        assert normalize_discount(cur, orig, raw_discount="-18%") == 18

        # Edge cases
        assert normalize_discount(cur, Decimal("0.00")) == 0
        assert normalize_discount(cur, None) == 0

    def test_normalize_vietnamese_product_url(self):
        url = normalize_product_url(shop_id=123456, item_id=789012)
        assert url == "https://shopee.vn/product/123456/789012"

        url_with_title = normalize_product_url(
            shop_id=123456,
            item_id=789012,
            name="Áo Thun Nam Cotton Thoáng Khí Cao Cấp",
        )
        assert "ao-thun-nam-cotton-thoang-khi-cao-cap-i.123456.789012" in url_with_title


class TestShopeeUrlIdExtraction:
    """Extract shop_id and item_id from various Shopee URL formats."""

    def test_extract_from_product_path(self):
        url = "https://shopee.vn/product/88231245/19283746501"
        shop_id, item_id = extract_ids_from_url(url)
        assert shop_id == 88231245
        assert item_id == 19283746501

    def test_extract_from_slug_with_i_dot_pattern(self):
        url = "https://shopee.vn/Chu%E1%BB%99t-Kh%C3%B4ng-D%C3%A2y-Logitech-M331-Silent-Plus-i.12345678.87654321?sp_atk=abcd"
        shop_id, item_id = extract_ids_from_url(url)
        assert shop_id == 12345678
        assert item_id == 87654321

    def test_extract_from_universal_link(self):
        url = "https://shopee.vn/universal-link/product/99999/88888"
        shop_id, item_id = extract_ids_from_url(url)
        assert shop_id == 99999
        assert item_id == 88888

    def test_extract_from_query_params(self):
        url = "https://shopee.vn/product?shop_id=112233&item_id=445566"
        shop_id, item_id = extract_ids_from_url(url)
        assert shop_id == 112233
        assert item_id == 445566

    def test_extract_from_invalid_url(self):
        shop_id, item_id = extract_ids_from_url("https://example.com/not-shopee")
        assert shop_id is None
        assert item_id is None

