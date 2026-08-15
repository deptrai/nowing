"""Red-phase unit tests for FastCrawler & Multi-Layer Anti-SSRF (Story 21.10)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from selectolax.parser import HTMLParser

# Target modules to be implemented in Story 21.10:
# from app.proprietary.platforms.crawler.fast_crawler import (
#     FastCrawler,
#     SSRFProtectionError,
#     extract_json_ld_metadata,
#     normalize_target_url,
#     validate_safe_ip,
# )

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. URL Normalization Tests (AC-1)
# ---------------------------------------------------------------------------
class TestUrlNormalization:
    """Test URL normalization logic."""

    def test_normalize_url_prepends_https_when_missing(self) -> None:
        """Should auto-prepend 'https://' if scheme is omitted."""
        from app.proprietary.platforms.crawler.fast_crawler import normalize_target_url

        assert normalize_target_url("vinhomes.vn") == "https://vinhomes.vn"
        assert (
            normalize_target_url("topcv.vn/tuyen-dung") == "https://topcv.vn/tuyen-dung"
        )

    def test_normalize_url_strips_tracking_query_params(self) -> None:
        """Should strip utm_*, fbclid, gclid, and ref tracking parameters."""
        from app.proprietary.platforms.crawler.fast_crawler import normalize_target_url

        url = "https://haravan.com/pricing?utm_source=facebook&utm_medium=cpc&fbclid=IwAR123&ref=banner"
        assert normalize_target_url(url) == "https://haravan.com/pricing"

    def test_normalize_url_preserves_legitimate_query_params(self) -> None:
        """Should preserve functional query parameters (e.g. search, page, id)."""
        from app.proprietary.platforms.crawler.fast_crawler import normalize_target_url

        url = "https://example.com/search?q=oceanpark&page=2&utm_source=google"
        assert (
            normalize_target_url(url) == "https://example.com/search?q=oceanpark&page=2"
        )

    def test_normalize_url_rejects_non_http_schemes(self) -> None:
        """Should reject file://, gopher://, ftp://, javascript:// schemes."""
        from app.proprietary.platforms.crawler.fast_crawler import (
            SSRFProtectionError,
            normalize_target_url,
        )

        with pytest.raises((ValueError, SSRFProtectionError)):
            normalize_target_url("file:///etc/passwd")

        with pytest.raises((ValueError, SSRFProtectionError)):
            normalize_target_url("gopher://127.0.0.1:6379/_")


# ---------------------------------------------------------------------------
# 2. SSRF & DNS Rebinding Protection Tests (AC-1, AC-2)
# ---------------------------------------------------------------------------
class TestSSRFProtection:
    """Test multi-layer SSRF, private subnet, and DNS rebinding protections."""

    @pytest.mark.asyncio
    async def test_validate_safe_ip_blocks_ipv4_private_subnets(self) -> None:
        """Should reject all RFC 1918 private subnets."""
        from app.proprietary.platforms.crawler.fast_crawler import validate_safe_ip

        private_ips = [
            "127.0.0.1",
            "127.0.0.2",
            "10.0.0.1",
            "10.254.0.1",
            "172.16.0.1",
            "172.31.255.255",
            "192.168.1.1",
            "192.168.0.254",
            "0.0.0.0",
        ]
        for ip in private_ips:
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.getaddrinfo = AsyncMock(
                    return_value=[(2, 1, 6, "", (ip, 80))]
                )
                is_safe = await validate_safe_ip(f"test-domain-{ip}.com")
                assert is_safe is False, f"IP {ip} should be rejected as private/unsafe"

    @pytest.mark.asyncio
    async def test_validate_safe_ip_blocks_cloud_metadata_endpoint(self) -> None:
        """Should reject AWS/GCP/DigitalOcean metadata IP 169.254.169.254."""
        from app.proprietary.platforms.crawler.fast_crawler import validate_safe_ip

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.getaddrinfo = AsyncMock(
                return_value=[(2, 1, 6, "", ("169.254.169.254", 80))]
            )
            is_safe = await validate_safe_ip("metadata.aws.internal")
            assert is_safe is False

    @pytest.mark.asyncio
    async def test_validate_safe_ip_blocks_ipv6_loopback(self) -> None:
        """Should reject IPv6 loopback (::1) and link-local addresses."""
        from app.proprietary.platforms.crawler.fast_crawler import validate_safe_ip

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.getaddrinfo = AsyncMock(
                return_value=[(10, 1, 6, "", ("::1", 80, 0, 0))]
            )
            is_safe = await validate_safe_ip("ipv6-loopback.internal")
            assert is_safe is False

    @pytest.mark.asyncio
    async def test_validate_safe_ip_allows_public_ips(self) -> None:
        """Should allow valid public routable IP addresses."""
        from app.proprietary.platforms.crawler.fast_crawler import validate_safe_ip

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.getaddrinfo = AsyncMock(
                return_value=[(2, 1, 6, "", ("1.1.1.1", 80))]
            )
            is_safe = await validate_safe_ip("cloudflare.com")
            assert is_safe is True

    @pytest.mark.asyncio
    async def test_crawler_blocks_redirect_to_internal_ip(self) -> None:
        """Redirect interceptor should block 301/302 hop pointing to internal IP."""
        from app.proprietary.platforms.crawler.fast_crawler import (
            FastCrawler,
            SSRFProtectionError,
        )

        crawler = FastCrawler()

        # Mock initial 302 redirect response pointing to http://127.0.0.1:8000/internal
        mock_response_302 = MagicMock()
        mock_response_302.status_code = 302
        mock_response_302.headers = {"Location": "http://127.0.0.1:8000/admin"}

        with (
            patch.object(
                crawler, "_send_raw_request", AsyncMock(return_value=mock_response_302)
            ),
            pytest.raises(SSRFProtectionError),
        ):
            await crawler.fetch_and_parse("https://malicious-public-site.com/redirect")


# ---------------------------------------------------------------------------
# 3. HTML & OpenGraph / JSON-LD Extraction Tests (AC-3)
# ---------------------------------------------------------------------------
class TestHtmlMetadataExtraction:
    """Test selectolax-based extraction for OG, Schema JSON-LD @graph, and text."""

    SAMPLE_HTML = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <title>Vinhomes Ocean Park - Thành phố Biển Hồ</title>
        <meta name="description" content="Đại đô thị Vinhomes Ocean Park Gia Lâm Hà Nội với biển hồ nước mặn 6.1ha.">
        <meta name="keywords" content="vinhomes ocean park, biet thu gia lam, chung cu cao cap">
        <meta property="og:title" content="Vinhomes Ocean Park 1 2 3">
        <meta property="og:description" content="Khu đô thị đẳng cấp quốc tế phía Đông Hà Nội.">
        <meta property="og:image" content="https://vinhomes.vn/og-oceanpark.jpg">
        <meta property="og:site_name" content="Vinhomes">
        <meta property="og:type" content="website">
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "RealEstateListing",
                    "name": "Vinhomes Ocean Park",
                    "description": "Dự án biệt thự và chung cư cao cấp",
                    "offers": {
                        "@type": "AggregateOffer",
                        "priceCurrency": "VND",
                        "lowPrice": "2500000000",
                        "highPrice": "50000000000"
                    }
                },
                {
                    "@type": "Organization",
                    "name": "Tập đoàn Vingroup",
                    "url": "https://vingroup.net"
                }
            ]
        }
        </script>
    </head>
    <body>
        <nav><a href="/home">Trang chủ</a><a href="/contact">Liên hệ</a></nav>
        <header><h1>Vinhomes Ocean Park - Nơi Đáng Sống Bậc Nhất</h1></header>
        <main>
            <h2>Vị trí đắc địa tại cửa ngõ phía Đông Thủ đô</h2>
            <p>Vinhomes Ocean Park sở hữu kết nối giao thông đồng bộ qua cao tốc Hà Nội - Hải Phòng...</p>
            <h2>Hệ thống tiện ích All-In-One</h2>
            <p>Trường học Vinschool, Bệnh viện Vinmec, Trung tâm thương mại Vincom Mega Mall...</p>
        </main>
        <footer><p>Bản quyền thuộc về Vinhomes 2026</p></footer>
    </body>
    </html>
    """

    def test_extract_opengraph_tags(self) -> None:
        """Should accurately extract all og:* metadata."""
        from app.proprietary.platforms.crawler.fast_crawler import FastCrawler

        crawler = FastCrawler()
        tree = HTMLParser(self.SAMPLE_HTML)
        og = crawler.extract_opengraph(tree)

        assert og["og:title"] == "Vinhomes Ocean Park 1 2 3"
        assert og["og:description"] == "Khu đô thị đẳng cấp quốc tế phía Đông Hà Nội."
        assert og["og:image"] == "https://vinhomes.vn/og-oceanpark.jpg"
        assert og["og:site_name"] == "Vinhomes"
        assert og["og:type"] == "website"

    def test_extract_json_ld_metadata_with_graph_flattening(self) -> None:
        """Should recursively flatten and extract items in @graph JSON-LD."""
        from app.proprietary.platforms.crawler.fast_crawler import (
            extract_json_ld_metadata,
        )

        tree = HTMLParser(self.SAMPLE_HTML)
        schemas = extract_json_ld_metadata(tree)

        assert len(schemas) == 2
        types = [s.get("@type") for s in schemas]
        assert "RealEstateListing" in types
        assert "Organization" in types

    def test_extract_clean_body_text_bounded_to_2000_chars(self) -> None:
        """Should strip script/nav/footer and truncate text to 2000 chars."""
        from app.proprietary.platforms.crawler.fast_crawler import FastCrawler

        crawler = FastCrawler()
        tree = HTMLParser(self.SAMPLE_HTML)
        text = crawler.extract_clean_hero_text(tree, max_chars=2000)

        # Nav/footer elements should be filtered out
        assert "Trang chủ" not in text
        assert "Bản quyền thuộc về" not in text
        # Main content should be preserved
        assert "Vị trí đắc địa tại cửa ngõ" in text
        assert len(text) <= 2000
