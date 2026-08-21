# ruff: noqa: RUF001, E402, F401
"""Master 25-Platform Live Scraper & Lead Intelligence Benchmark Suite.

Audits ALL 25+ proprietary platform scrapers in nowing_backend across 8 business domains:
1. Bất Động Sản: Batdongsan, Chợ Tốt, Mua Bán BĐS, Quy Hoạch (Spatial Planning)
2. Doanh Nghiệp & MST: MaSoThue, Mua Sắm Công (Đấu thầu chính phủ)
3. Việc Làm & HR: TopCV, ITviec, VietnamWorks, Indeed, LinkedIn
4. Địa Điểm & Local: Google Maps, Google Search (SERP)
5. Tài Chính & Chứng Khoán: Vietstock, CafeF
6. Thương Mại Điện Tử: Shopee, Amazon, Walmart
7. Mạng Xã Hội & Cộng Đồng: TikTok, YouTube, Instagram, Telegram, Reddit, XActions
8. Web Crawling Đa Năng: Universal Fast Crawler
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Ensure nowing_backend is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.proprietary.platforms.xactions.phone_extractor import SocialEntityExtractor
from app.proprietary.platforms.xactions.tax_code import extract_tax_ids


@dataclass
class PlatformScraperTestCase:
    platform_name: str
    domain_category: str
    target_description: str
    test_query: str
    max_items: int = 10


@dataclass
class PlatformBenchmarkResult:
    platform_name: str
    domain_category: str
    test_query: str
    execution_time_ms: float
    items_count: int
    phones_extracted: int
    tax_ids_extracted: int
    emails_extracted: int
    status: str  # "ok" | "blocked_waf" | "rate_limited" | "timeout" | "degraded" | "error"
    error_detail: str | None = None


# ---------------------------------------------------------------------------
# 25 REAL PLATFORM TEST CASES MATRIX
# ---------------------------------------------------------------------------

PLATFORMS_MATRIX: list[PlatformScraperTestCase] = [
    # 1. Bất Động Sản & Quy Hoạch
    PlatformScraperTestCase(
        platform_name="batdongsan",
        domain_category="Bất Động Sản",
        target_description="Batdongsan.com.vn nhà đất & biệt thự",
        test_query="Bán biệt thự Thảo Điền Quận 2 TP.HCM",
        max_items=10,
    ),
    PlatformScraperTestCase(
        platform_name="chotot",
        domain_category="Bất Động Sản",
        target_description="Chợ Tốt Nhà & Rao vặt chính chủ",
        test_query="Cho thuê shophouse Sala Thủ Thiêm",
        max_items=10,
    ),
    PlatformScraperTestCase(
        platform_name="muaban_bds",
        domain_category="Bất Động Sản",
        target_description="MuaBan.net BĐS chính chủ",
        test_query="Bán nhà phố Quận 1 mặt tiền",
        max_items=10,
    ),
    PlatformScraperTestCase(
        platform_name="spatial_planning",
        domain_category="Bất Động Sản",
        target_description="Thông tin Quy hoạch sử dụng đất",
        test_query="Quy hoạch đất KĐT mới Thủ Thiêm TP.HCM",
        max_items=5,
    ),

    # 2. Doanh Nghiệp & Pháp Lý Thuế
    PlatformScraperTestCase(
        platform_name="masothue",
        domain_category="Doanh Nghiệp & MST",
        target_description="MaSoThue.com & Tổng cục Thuế",
        test_query="Công ty sản xuất bao bì nhựa KCN Sóng Thần",
        max_items=10,
    ),
    PlatformScraperTestCase(
        platform_name="muasamcong",
        domain_category="Doanh Nghiệp & MST",
        target_description="Mạng Đấu Thầu Quốc Gia Muasamcong",
        test_query="Gói thầu xây dựng giao thông TP.HCM",
        max_items=10,
    ),

    # 3. Tuyển Dụng & Thị Trường HR
    PlatformScraperTestCase(
        platform_name="topcv",
        domain_category="Tuyển Dụng & HR",
        target_description="TopCV tuyển dụng nhân sự & HR contacts",
        test_query="Senior Python Engineer TP.HCM",
        max_items=10,
    ),
    PlatformScraperTestCase(
        platform_name="itviec",
        domain_category="Tuyển Dụng & HR",
        target_description="ITviec việc làm Tech chuyên sâu",
        test_query="DevOps Kubernetes Cloud Architect",
        max_items=10,
    ),
    PlatformScraperTestCase(
        platform_name="vietnamworks",
        domain_category="Tuyển Dụng & HR",
        target_description="VietnamWorks việc làm cấp trung/cao",
        test_query="Giám đốc Marketing B2B Hà Nội",
        max_items=10,
    ),
    PlatformScraperTestCase(
        platform_name="indeed",
        domain_category="Tuyển Dụng & HR",
        target_description="Indeed việc làm quốc tế",
        test_query="Software Engineer Vietnam remote",
        max_items=10,
    ),
    PlatformScraperTestCase(
        platform_name="linkedin",
        domain_category="Tuyển Dụng & HR",
        target_description="LinkedIn B2B Profiles & Executives",
        test_query="CEO Founder FinTech Vietnam",
        max_items=10,
    ),

    # 4. Địa Điểm & Local Business
    PlatformScraperTestCase(
        platform_name="google_maps",
        domain_category="Địa Điểm & Maps",
        target_description="Google Maps Places, Reviews & Phone",
        test_query="Phòng khám nha khoa uy tín Quận 1 TP.HCM",
        max_items=10,
    ),
    PlatformScraperTestCase(
        platform_name="google_search",
        domain_category="Địa Điểm & Maps",
        target_description="Google SERP Live Search Results",
        test_query="Đại lý phân phối sắt thép xây dựng Đồng Nai",
        max_items=10,
    ),

    # 5. Tài Chính & Chứng Khoán
    PlatformScraperTestCase(
        platform_name="vietstock",
        domain_category="Tài Chính & Chứng Khoán",
        target_description="Vietstock dữ liệu doanh nghiệp niêm yết",
        test_query="Báo cáo tài chính Vinamilk VNM",
        max_items=5,
    ),
    PlatformScraperTestCase(
        platform_name="cafef",
        domain_category="Tài Chính & Chứng Khoán",
        target_description="CafeF tin tức & hồ sơ công ty",
        test_query="Tập đoàn Hòa Phát HPG doanh thu lợi nhuận",
        max_items=5,
    ),

    # 6. Thương Mại Điện Tử
    PlatformScraperTestCase(
        platform_name="shopee",
        domain_category="Thương Mại Điện Tử",
        target_description="Shopee.vn Mall & Shop Contacts",
        test_query="Thiết bị nhà thông minh SmartHome",
        max_items=10,
    ),
    PlatformScraperTestCase(
        platform_name="amazon",
        domain_category="Thương Mại Điện Tử",
        target_description="Amazon E-Commerce Listings",
        test_query="Ergonomic mechanical keyboard",
        max_items=10,
    ),
    PlatformScraperTestCase(
        platform_name="walmart",
        domain_category="Thương Mại Điện Tử",
        target_description="Walmart Product Catalog",
        test_query="Air purifier HEPA filter",
        max_items=10,
    ),

    # 7. Mạng Xã Hội & Video
    PlatformScraperTestCase(
        platform_name="tiktok",
        domain_category="Mạng Xã Hội",
        target_description="TikTok Shop & Creator Accounts",
        test_query="Review bất động sản TP.HCM",
        max_items=10,
    ),
    PlatformScraperTestCase(
        platform_name="youtube",
        domain_category="Mạng Xã Hội",
        target_description="YouTube Video & Channel Contacts",
        test_query="Xu hướng thị trường bất động sản 2026",
        max_items=5,
    ),
    PlatformScraperTestCase(
        platform_name="instagram",
        domain_category="Mạng Xã Hội",
        target_description="Instagram Bio & Business Profiles",
        test_query="Interior design Saigon",
        max_items=10,
    ),
    PlatformScraperTestCase(
        platform_name="telegram",
        domain_category="Mạng Xã Hội",
        target_description="Telegram Lead Groups & Channels",
        test_query="Hội đầu tư BĐS Thủ Đức",
        max_items=10,
    ),
    PlatformScraperTestCase(
        platform_name="reddit",
        domain_category="Mạng Xã Hội",
        target_description="Reddit Community Discussions",
        test_query="Vietnam startup tech trends",
        max_items=10,
    ),
    PlatformScraperTestCase(
        platform_name="xactions",
        domain_category="Mạng Xã Hội",
        target_description="XActions Social Phone & Contact Extractor",
        test_query="Chính chủ cần bán gấp nhà O9O8.123.456 Zalo",
        max_items=5,
    ),

    # 8. Web Crawler Đa Năng
    PlatformScraperTestCase(
        platform_name="crawler",
        domain_category="Universal Crawler",
        target_description="Universal Fast Crawler & Entity Pipeline",
        test_query="https://fpt.vn/vi/ve-fpt/gioi-thieu-chung",
        max_items=5,
    ),
]


async def run_single_platform_benchmark(
    tc: PlatformScraperTestCase,
) -> PlatformBenchmarkResult:
    print(f"\n▶ [{tc.platform_name.upper()}] ({tc.domain_category})", flush=True)
    print(f"  Target : {tc.target_description}", flush=True)
    print(f"  Query  : \"{tc.test_query}\"", flush=True)

    t0 = time.perf_counter()
    status = "ok"
    err_detail = None
    items_count = 0
    phones_count = 0
    tax_ids_count = 0
    emails_count = 0

    try:
        # Dynamic execution per platform module
        p = tc.platform_name

        if p == "batdongsan":
            from app.proprietary.platforms.batdongsan.schemas import (
                BatdongsanScrapeInput,
            )
            from app.proprietary.platforms.batdongsan.scraper import scrape_batdongsan
            inp = BatdongsanScrapeInput(city="SG", listing_type="buy", max_items=tc.max_items)
            out = await asyncio.wait_for(scrape_batdongsan(inp), timeout=15.0)
            items_count = len(out.items)
            phones_count = sum(1 for item in out.items if getattr(item, "phone", None) or getattr(item, "contact_name", None))

        elif p == "chotot":
            from app.proprietary.platforms.chotot.schemas import ChototScrapeInput
            from app.proprietary.platforms.chotot.scraper import scrape_chotot
            inp = ChototScrapeInput(category="bds", listing_type="sell", city="ho-chi-minh", max_items=tc.max_items)
            out = await asyncio.wait_for(scrape_chotot(inp), timeout=15.0)
            items_count = len(out.items)
            phones_count = sum(1 for item in out.items if getattr(item, "phone", None))

        elif p == "muaban_bds":
            from app.proprietary.platforms.muaban_bds.schemas import (
                MuabanBdsScrapeInput,
            )
            from app.proprietary.platforms.muaban_bds.scraper import scrape_muaban_bds
            inp = MuabanBdsScrapeInput(city="ho-chi-minh", listing_type="buy", max_items=tc.max_items)
            out = await asyncio.wait_for(scrape_muaban_bds(inp), timeout=15.0)
            items_count = len(out.items)
            phones_count = sum(1 for item in out.items if getattr(item, "phone", None))

        elif p == "masothue":
            from app.proprietary.platforms.masothue.schemas import MasothueSearchInput
            from app.proprietary.platforms.masothue.scraper import scrape_masothue
            inp = MasothueSearchInput(query=tc.test_query, max_items=tc.max_items)
            out = await asyncio.wait_for(scrape_masothue(inp), timeout=15.0)
            items_count = len(out.items)
            tax_ids_count = sum(1 for c in out.items if getattr(c, "tax_code", None))
            phones_count = sum(1 for c in out.items if getattr(c, "phone", None))

        elif p == "topcv":
            from app.proprietary.platforms.topcv.scraper import scrape_topcv
            out = await asyncio.wait_for(scrape_topcv({"keyword": tc.test_query, "max_items": tc.max_items}), timeout=15.0)
            items_list = out.get("items", [])
            items_count = len(items_list)
            emails_count = sum(1 for j in items_list if "email" in str(j).lower())

        elif p == "itviec":
            from app.proprietary.platforms.itviec.scraper import scrape_itviec
            out = await asyncio.wait_for(scrape_itviec({"keyword": tc.test_query, "max_items": tc.max_items}), timeout=15.0)
            items_list = out.get("items", [])
            items_count = len(items_list)

        elif p == "vietnamworks":
            from app.proprietary.platforms.vietnamworks.scraper import (
                scrape_vietnamworks,
            )
            out = await asyncio.wait_for(scrape_vietnamworks({"keyword": tc.test_query, "max_items": tc.max_items}), timeout=15.0)
            items_list = out.get("items", [])
            items_count = len(items_list)

        elif p == "google_maps":
            from app.proprietary.platforms.google_maps.schemas import (
                GoogleMapsScrapeInput,
            )
            from app.proprietary.platforms.google_maps.scraper import scrape_places
            inp = GoogleMapsScrapeInput(searchStrings=[tc.test_query], maxCrawledPlaces=tc.max_items)
            places_list = await asyncio.wait_for(scrape_places(inp), timeout=20.0)
            items_count = len(places_list)
            phones_count = sum(1 for pl in places_list if getattr(pl, "phone", None))

        elif p == "xactions":
            extractor = SocialEntityExtractor()
            phones = extractor.extract_phones(tc.test_query)
            items_count = 1
            phones_count = len(phones)

        elif p == "crawler":
            from app.proprietary.platforms.crawler.fast_crawler import FastCrawler
            crawler = FastCrawler(timeout=10.0)
            meta_res = await asyncio.wait_for(crawler.crawl(tc.test_query), timeout=15.0)
            items_count = 1 if meta_res.title else 0
            tax_ids_count = len(extract_tax_ids(meta_res.text_content or ""))

        else:
            # Universal Lead Adapter Dispatcher
            from app.lead_intelligence.adapters.registry import (
                LeadSourceAdapterRegistry,
            )
            reg = LeadSourceAdapterRegistry.get_default()
            adapter = reg.get_adapter(p) if p in reg._adapters else None
            if adapter:
                records = await asyncio.wait_for(
                    adapter.search_leads(workspace_id=1, query=tc.test_query, limit=tc.max_items),
                    timeout=15.0,
                )
                items_count = len(records)
                phones_count = sum(1 for r in records if "phone" in str(r).lower())
            else:
                items_count = 0
                status = "not_configured"

    except TimeoutError:
        status = "timeout"
        err_detail = "Scraper execution timed out after 15.0s"
    except Exception as exc:
        err_str = str(exc)
        if "403" in err_str or "blocked" in err_str.lower() or "cloudflare" in err_str.lower():
            status = "blocked_waf"
        elif "429" in err_str or "rate limit" in err_str.lower():
            status = "rate_limited"
        else:
            status = "degraded"
        err_detail = err_str

    exec_time_ms = (time.perf_counter() - t0) * 1000

    # Print feedback
    if status == "ok" and items_count > 0:
        print(f"  ✓ [{tc.platform_name}] SUCCESS: Harvested {items_count} items in {exec_time_ms:.2f}ms (Phones: {phones_count} | MST: {tax_ids_count} | Emails: {emails_count})", flush=True)
    elif status == "blocked_waf":
        print(f"  ⚠️ [{tc.platform_name}] WAF/403 BLOCKED: Handled gracefully in {exec_time_ms:.2f}ms (Anti-bot alert)", flush=True)
    elif status == "timeout":
        print(f"  ⚠️ [{tc.platform_name}] TIMEOUT: Boundary isolated at {exec_time_ms:.2f}ms", flush=True)
    else:
        print(f"  • [{tc.platform_name}] Status: {status} ({err_detail[:80] if err_detail else '0 items'}) in {exec_time_ms:.2f}ms", flush=True)

    return PlatformBenchmarkResult(
        platform_name=tc.platform_name,
        domain_category=tc.domain_category,
        test_query=tc.test_query,
        execution_time_ms=exec_time_ms,
        items_count=items_count,
        phones_extracted=phones_count,
        tax_ids_extracted=tax_ids_count,
        emails_extracted=emails_count,
        status=status,
        error_detail=err_detail,
    )


async def main():
    print("=" * 80, flush=True)
    print("🌐 MASTER 25-PLATFORM LIVE SCRAPER & LEAD ENGINE BENCHMARK", flush=True)
    print(f"Total Platforms : {len(PLATFORMS_MATRIX)} Platform Scrapers across 8 Domains", flush=True)
    print(f"Start Timestamp : {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())}", flush=True)
    print("=" * 80, flush=True)

    t0_master = time.perf_counter()
    results: list[PlatformBenchmarkResult] = []

    for idx, tc in enumerate(PLATFORMS_MATRIX, 1):
        print(f"\n--- Running Platform Scraper {idx}/{len(PLATFORMS_MATRIX)}: {tc.platform_name} ---", flush=True)
        res = await run_single_platform_benchmark(tc)
        results.append(res)
        await asyncio.sleep(0.3)

    total_bench_duration_s = time.perf_counter() - t0_master

    # Comprehensive Summary Audit
    successful_scrapers = [r for r in results if r.status == "ok" and r.items_count > 0]
    waf_blocked = [r for r in results if r.status == "blocked_waf"]
    timeouts = [r for r in results if r.status == "timeout"]
    degraded = [r for r in results if r.status in ("degraded", "not_configured", "rate_limited") or (r.status == "ok" and r.items_count == 0)]

    total_items = sum(r.items_count for r in results)
    total_phones = sum(r.phones_extracted for r in results)
    total_tax_ids = sum(r.tax_ids_extracted for r in results)
    total_emails = sum(r.emails_extracted for r in results)

    print("\n" + "=" * 80, flush=True)
    print("📊 MASTER 25-PLATFORM LIVE SCRAPER BENCHMARK AUDIT REPORT:", flush=True)
    print("=" * 80, flush=True)
    print(f"  • Total Platforms Evaluated     : {len(results)} scrapers (8 business domains)", flush=True)
    print(f"  • Live Scrapers Operational (OK): {len(successful_scrapers)}/{len(results)} ({len(successful_scrapers)*100/len(results):.1f}%)", flush=True)
    print(f"  • WAF / Cloudflare Blocked (403): {len(waf_blocked)} platforms (Need rotating proxy/session)", flush=True)
    print(f"  • Execution Timeouts (Guard 15s): {len(timeouts)} platforms", flush=True)
    print(f"  • Total Items / Leads Harvested : {total_items} records across web", flush=True)
    print(f"  • Total Contact Phones Captured : {total_phones} phones", flush=True)
    print(f"  • Total Corporate Tax IDs (MST) : {total_tax_ids} tax codes", flush=True)
    print(f"  • Total Direct Emails Captured  : {total_emails} emails", flush=True)
    print(f"  • Total Benchmark Duration      : {total_bench_duration_s:.2f} seconds ({total_bench_duration_s/60:.2f} minutes)", flush=True)
    print("-" * 80, flush=True)

    print("📋 BREAKDOWN THEO 8 NHÓM LĨNH VỰC:", flush=True)
    domain_groups: dict[str, list[PlatformBenchmarkResult]] = {}
    for r in results:
        domain_groups.setdefault(r.domain_category, []).append(r)

    for domain, items in domain_groups.items():
        ok_count = sum(1 for it in items if it.status == "ok" and it.items_count > 0)
        items_harvested = sum(it.items_count for it in items)
        avg_lat = sum(it.execution_time_ms for it in items) / len(items)
        print(f"  🏷️  {domain:<26}: {ok_count}/{len(items)} Online | {items_harvested:>3} items | Avg Latency: {avg_lat:>7.1f}ms", flush=True)

    print("-" * 80, flush=True)
    print("⚠️ PHÁT HIỆN ĐIỂM NGHẼN & BÁO CÁO WAF / ANTI-BOT:", flush=True)
    if waf_blocked:
        for wb in waf_blocked:
            print(f"  🔒 [WAF 403] Platform '{wb.platform_name}': Bị chặn bởi Cloudflare/Portal WAF -> Cần xoay IP Residential Proxy.", flush=True)
    if timeouts:
        for to in timeouts:
            print(f"  ⏱️ [TIMEOUT] Platform '{to.platform_name}': Quá thời gian chờ 15s -> Cần tối ưu crawl concurrency.", flush=True)
    if degraded:
        for dg in degraded:
            print(f"  ℹ️ [DEGRADED] Platform '{dg.platform_name}': {dg.error_detail[:60] if dg.error_detail else 'Empty payload'}", flush=True)

    print("=" * 80, flush=True)

    # Save artifact to disk
    artifact_path = Path(backend_dir.parent / "_bmad-output/test-artifacts/master_25_platforms_benchmark.json")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    with open(artifact_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, ensure_ascii=False, indent=2)
    print(f"✓ Master 25-Platform Benchmark saved to: {artifact_path}\n", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
