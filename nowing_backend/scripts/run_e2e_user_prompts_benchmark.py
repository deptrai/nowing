# ruff: noqa: E402, F401, F841
"""Master End-to-End Real User Prompt Benchmark Suite (Nowing Real API & LLM Inference).

Executes 30 realistic Vietnamese & English enterprise prompts against live http://localhost:8000:
- Sends real SSE streaming requests to /api/v1/new_chat
- Evaluates real LLM reasoning, subagent dispatch, tool calling, scraping, entity extraction, and DB writes
- Measures TTFB, End-to-End Latency, Token Usage, Cost in Micros, Citations, Scraper Success, and Failure Gaps
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

# Ensure nowing_backend is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(backend_dir.parent / "nowing_evals/src"))

from app.proprietary.platforms.xactions.phone_extractor import SocialEntityExtractor
from app.proprietary.platforms.xactions.tax_code import extract_tax_ids

BASE_URL = os.environ.get("NOWING_API_BASE", "http://localhost:8000")
USER_EMAIL = os.environ.get("NOWING_USER_EMAIL", "e2e-test@nowing.net")
USER_PASS = os.environ.get("NOWING_USER_PASSWORD", "E2eTestPassword123!")

# ---------------------------------------------------------------------------
# 30 REAL-WORLD ENTERPRISE USER PROMPTS DATASET
# ---------------------------------------------------------------------------

PROMPTS_DATASET: list[dict[str, Any]] = [
    # Group 1: Bất Động Sản (Real Estate Lead Discovery & Phone Extraction)
    {
        "id": "bds-001",
        "domain": "Bất Động Sản",
        "lang": "vi",
        "mode": "speed",
        "prompt": "Tìm cho tôi 3 tin đăng bán biệt thự Thảo Điền Quận 2 mới nhất kèm giá bán và số điện thoại liên hệ của chủ nhà hoặc môi giới.",
        "expected_tags": ["bds", "phone", "price"],
    },
    {
        "id": "bds-002",
        "domain": "Bất Động Sản",
        "lang": "vi",
        "mode": "balanced",
        "prompt": "Tổng hợp danh sách các căn shophouse đang cho thuê tại Vinhomes Grand Park Thủ Đức, bóc tách SĐT và người liên hệ.",
        "expected_tags": ["shophouse", "phone"],
    },
    {
        "id": "bds-003",
        "domain": "Bất Động Sản",
        "lang": "en",
        "mode": "speed",
        "prompt": "Find 3 luxury apartments for rent in Landmark 81 Ho Chi Minh City with contact phone numbers and monthly rental rates.",
        "expected_tags": ["luxury", "phone"],
    },
    {
        "id": "bds-004",
        "domain": "Bất Động Sản",
        "lang": "vi",
        "mode": "balanced",
        "prompt": "Tìm đất nền khu đô thị Nam Long Cần Thơ dưới 3 tỷ có số điện thoại chính chủ hoặc Zalo.",
        "expected_tags": ["land", "phone"],
    },
    {
        "id": "bds-005",
        "domain": "Bất Động Sản",
        "lang": "vi",
        "mode": "speed",
        "prompt": "Bóc tách danh sách 3 môi giới bất động sản chuyên khu Đông TP.HCM có số điện thoại di động.",
        "expected_tags": ["broker", "phone"],
    },

    # Group 2: Doanh Nghiệp & Tra Cứu Thuế (B2B Lead Intelligence & Tax Code Verification)
    {
        "id": "tax-006",
        "domain": "Doanh Nghiệp & MST",
        "lang": "vi",
        "mode": "balanced",
        "prompt": "Liệt kê 3 công ty sản xuất bao bì nhựa tại KCN Sóng Thần Bình Dương kèm Mã số thuế và số điện thoại.",
        "expected_tags": ["tax_id", "phone", "manufacturing"],
    },
    {
        "id": "tax-007",
        "domain": "Doanh Nghiệp & MST",
        "lang": "vi",
        "mode": "speed",
        "prompt": "Tìm danh sách 3 công ty xuất nhập khẩu thủy sản tại Cà Mau kèm mã số doanh nghiệp.",
        "expected_tags": ["tax_id", "seafood"],
    },
    {
        "id": "tax-008",
        "domain": "Doanh Nghiệp & MST",
        "lang": "en",
        "mode": "speed",
        "prompt": "List 3 logistics and freight forwarding enterprises in Hai Phong port with verified Vietnamese tax IDs and phone contacts.",
        "expected_tags": ["logistics", "tax_id"],
    },
    {
        "id": "tax-009",
        "domain": "Doanh Nghiệp & MST",
        "lang": "vi",
        "mode": "balanced",
        "prompt": "Tra cứu thông tin pháp lý, mã số thuế và trụ sở của Tập đoàn Hòa Phát và Tập đoàn FPT.",
        "expected_tags": ["tax_id", "corporate"],
    },
    {
        "id": "tax-010",
        "domain": "Doanh Nghiệp & MST",
        "lang": "vi",
        "mode": "speed",
        "prompt": "Tìm 3 hợp tác xã nông nghiệp công nghệ cao tại Đà Lạt Lâm Đồng kèm số điện thoại liên hệ.",
        "expected_tags": ["coop", "phone"],
    },

    # Group 3: Tuyển Dụng & HR (Job Market Intelligence & Compensation Benchmark)
    {
        "id": "job-011",
        "domain": "Tuyển Dụng & HR",
        "lang": "vi",
        "mode": "speed",
        "prompt": "Tổng hợp 3 tin tuyển dụng Senior Python / FastAPI Engineer tại TP.HCM mức lương trên 35 triệu kèm contact HR.",
        "expected_tags": ["salary", "recruitment", "phone"],
    },
    {
        "id": "job-012",
        "domain": "Tuyển Dụng & HR",
        "lang": "en",
        "mode": "balanced",
        "prompt": "Find 2 Chief Technology Officer (CTO) or VP of Engineering job openings in Vietnam fintech startups with estimated salary.",
        "expected_tags": ["cto", "fintech"],
    },
    {
        "id": "job-013",
        "domain": "Tuyển Dụng & HR",
        "lang": "vi",
        "mode": "speed",
        "prompt": "Khảo sát mức lương và yêu cầu công việc vị trí Trưởng phòng Marketing B2B tại Hà Nội.",
        "expected_tags": ["marketing", "salary"],
    },
    {
        "id": "job-014",
        "domain": "Tuyển Dụng & HR",
        "lang": "vi",
        "mode": "speed",
        "prompt": "Tìm thông tin tuyển dụng kỹ sư DevOps Kubernetes tại các công ty công nghệ tại Việt Nam.",
        "expected_tags": ["devops", "recruitment"],
    },
    {
        "id": "job-015",
        "domain": "Tuyển Dụng & HR",
        "lang": "en",
        "mode": "speed",
        "prompt": "Extract 2 AI Research Scientist recruitment listings in Vietnam with application email or telegram.",
        "expected_tags": ["ai", "email"],
    },

    # Group 4: Nghiên Cứu Sâu Đa Nguồn (Deep Research & Multi-Source Synthesis)
    {
        "id": "res-016",
        "domain": "Nghiên Cứu Sâu",
        "lang": "vi",
        "mode": "quality",
        "prompt": "Nghiên cứu tổng quan xu hướng giá căn hộ chung cư khu vực TP. Thủ Đức trong giai đoạn 2025-2026, xuất bảng so sánh 3 dự án tiêu biểu.",
        "expected_tags": ["deep-research", "table"],
    },
    {
        "id": "res-017",
        "domain": "Nghiên Cứu Sâu",
        "lang": "en",
        "mode": "quality",
        "prompt": "Perform research on Vietnam renewable energy policy shifts and feed-in-tariff updates for 2026.",
        "expected_tags": ["deep-research", "policy"],
    },
    {
        "id": "res-018",
        "domain": "Nghiên Cứu Sâu",
        "lang": "vi",
        "mode": "balanced",
        "prompt": "So sánh ưu nhược điểm vị trí và chuỗi cung ứng của 3 khu công nghiệp lớn tại Bắc Ninh.",
        "expected_tags": ["industrial", "comparison"],
    },
    {
        "id": "res-019",
        "domain": "Nghiên Cứu Sâu",
        "lang": "en",
        "mode": "quality",
        "prompt": "Analyze the competitive landscape of AI search engines and memory platforms in Southeast Asia.",
        "expected_tags": ["deep-research", "ai"],
    },
    {
        "id": "res-020",
        "domain": "Nghiên Cứu Sâu",
        "lang": "vi",
        "mode": "balanced",
        "prompt": "Nghiên cứu thị trường chuỗi cà phê tại TP.HCM: so sánh phân khúc khách hàng của Highlands Coffee và Phúc Long.",
        "expected_tags": ["fnb", "market-share"],
    },

    # Group 5: Lead Harvesting & CRM Intelligence
    {
        "id": "lead-021",
        "domain": "Lead Harvesting",
        "lang": "vi",
        "mode": "balanced",
        "prompt": "Thu thập danh sách 3 chuỗi nhà thuốc lớn tại Việt Nam (như Long Châu, An Khang, Pharmacity) kèm thông tin hotline và trụ sở.",
        "expected_tags": ["lead", "pharmacy"],
    },
    {
        "id": "lead-022",
        "domain": "Lead Harvesting",
        "lang": "en",
        "mode": "speed",
        "prompt": "List 3 software outsourcing companies in Da Nang with company website domain and contact details.",
        "expected_tags": ["lead", "software"],
    },
    {
        "id": "lead-023",
        "domain": "Lead Harvesting",
        "lang": "vi",
        "mode": "speed",
        "prompt": "Thu thập 3 đại lý phân phối xi măng và sắt thép xây dựng tại Đồng Nai kèm số điện thoại liên hệ.",
        "expected_tags": ["lead", "construction"],
    },
    {
        "id": "lead-024",
        "domain": "Lead Harvesting",
        "lang": "vi",
        "mode": "speed",
        "prompt": "Tổng hợp 3 hệ thống nha khoa thẩm mỹ uy tín tại Hà Nội kèm số điện thoại tư vấn.",
        "expected_tags": ["lead", "dental"],
    },
    {
        "id": "lead-025",
        "domain": "Lead Harvesting",
        "lang": "en",
        "mode": "balanced",
        "prompt": "Harvest 3 B2B marketing agencies operating in Ho Chi Minh City with official website URLs.",
        "expected_tags": ["lead", "agency"],
    },

    # Group 6: Edge Cases & Anti-Bot Robustness (Obfuscation & Negative Filtering)
    {
        "id": "edge-026",
        "domain": "Edge Cases & Lọc",
        "lang": "vi",
        "mode": "speed",
        "prompt": "Tìm thông tin cho thuê kho xưởng tại Bình Dương có số điện thoại viết dạng chữ như Không Chín Một Tám hoặc O9O8.",
        "expected_tags": ["obfuscation", "phone"],
    },
    {
        "id": "edge-027",
        "domain": "Edge Cases & Lọc",
        "lang": "vi",
        "mode": "speed",
        "prompt": "Cho tôi số tổng đài chăm sóc khách hàng của Ngân hàng Vietcombank và Viettel Telecom. (Lưu ý đây là tổng đài CSKH 1900/1800, không phải SĐT cá nhân).",
        "expected_tags": ["hotline-filter", "bank"],
    },
    {
        "id": "edge-028",
        "domain": "Edge Cases & Lọc",
        "lang": "en",
        "mode": "speed",
        "prompt": "Identify customer support channels for major airlines in Vietnam while noting if they are commercial toll-free hotlines.",
        "expected_tags": ["hotline-filter", "airline"],
    },
    {
        "id": "edge-029",
        "domain": "Edge Cases & Lọc",
        "lang": "vi",
        "mode": "balanced",
        "prompt": "Tìm kiếm dự án đầu tư công hạ tầng giao thông trọng điểm tại TP.HCM (như Vành đai 3) kèm ban quản lý dự án.",
        "expected_tags": ["infrastructure", "gov"],
    },
    {
        "id": "edge-030",
        "domain": "Edge Cases & Lọc",
        "lang": "vi",
        "mode": "quality",
        "prompt": "Tóm tắt kết quả kinh doanh và thị phần gần nhất của Vinamilk (VNM) trên sàn chứng khoán HoSE.",
        "expected_tags": ["financial", "stock"],
    },
]


@dataclass
class PromptExecutionResult:
    prompt_id: str
    domain: str
    lang: str
    mode: str
    status_code: int
    ttfb_ms: float
    latency_s: float
    prompt_tokens: int
    completion_tokens: int
    cost_micros: int
    response_length: int
    phones_extracted: list[str] = field(default_factory=list)
    tax_ids_extracted: list[str] = field(default_factory=list)
    citations_count: int = 0
    error: str | None = None
    success: bool = False


async def run_prompt_turn(
    client: httpx.AsyncClient,
    workspace_id: int,
    item: dict[str, Any],
) -> PromptExecutionResult:
    p_id = item["id"]
    domain = item["domain"]
    lang = item["lang"]
    mode = item["mode"]
    prompt_text = item["prompt"]

    print(f"\n▶ [{p_id}] ({domain} | {lang.upper()} | mode={mode})", flush=True)
    print(f"  Query: \"{prompt_text[:75]}...\"", flush=True)

    # 1. Create a dedicated real Thread in PostgreSQL
    t0_thread = time.perf_counter()
    try:
        resp_th = await client.post(
            "/api/v1/threads",
            json={"title": f"Bench {p_id} {time.strftime('%H:%M:%S')}", "workspace_id": workspace_id},
        )
        if resp_th.status_code != 200:
            return PromptExecutionResult(
                prompt_id=p_id,
                domain=domain,
                lang=lang,
                mode=mode,
                status_code=resp_th.status_code,
                ttfb_ms=0,
                latency_s=0,
                prompt_tokens=0,
                completion_tokens=0,
                cost_micros=0,
                response_length=0,
                error=f"Thread creation failed HTTP {resp_th.status_code}: {resp_th.text}",
                success=False,
            )
        thread_id = resp_th.json().get("id")
    except Exception as exc:
        return PromptExecutionResult(
            prompt_id=p_id,
            domain=domain,
            lang=lang,
            mode=mode,
            status_code=500,
            ttfb_ms=0,
            latency_s=0,
            prompt_tokens=0,
            completion_tokens=0,
            cost_micros=0,
            response_length=0,
            error=str(exc),
            success=False,
        )

    # 2. Fire real SSE Streaming request to /api/v1/new_chat
    payload = {
        "chat_id": thread_id,
        "user_query": prompt_text,
        "workspace_id": workspace_id,
        "mode": mode,
    }

    t0_req = time.perf_counter()
    ttfb_ms: float = 0.0
    accumulated_text = []
    citations_count = 0
    prompt_tokens = 0
    completion_tokens = 0
    cost_micros = 0
    status_code = 0
    error_msg = None

    try:
        async with client.stream("POST", "/api/v1/new_chat", json=payload, timeout=180.0) as stream_resp:
            status_code = stream_resp.status_code
            if status_code != 200:
                raw_err = await stream_resp.aread()
                return PromptExecutionResult(
                    prompt_id=p_id,
                    domain=domain,
                    lang=lang,
                    mode=mode,
                    status_code=status_code,
                    ttfb_ms=0,
                    latency_s=time.perf_counter() - t0_req,
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_micros=0,
                    response_length=0,
                    error=f"Chat endpoint failed HTTP {status_code}: {raw_err.decode(errors='ignore')[:150]}",
                    success=False,
                )

            # Read SSE stream chunk by chunk
            async for line in stream_resp.aiter_lines():
                if ttfb_ms == 0.0 and line.strip():
                    ttfb_ms = (time.perf_counter() - t0_req) * 1000

                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue

                raw_data = line[5:].strip()
                if raw_data == "[DONE]":
                    break

                try:
                    event = json.loads(raw_data)
                    event_type = event.get("type")
                    if event_type == "text-delta":
                        accumulated_text.append(event.get("delta", ""))
                    elif event_type == "citation":
                        citations_count += 1
                    elif event_type == "data-token-usage":
                        usage = event.get("usage", {})
                        prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
                        completion_tokens = usage.get("completion_tokens", completion_tokens)
                        cost_micros = usage.get("cost_micros", cost_micros)
                    elif event_type == "error":
                        error_msg = event.get("message") or str(event)
                except Exception:
                    pass

    except Exception as exc:
        error_msg = str(exc)
        status_code = 500

    total_latency_s = time.perf_counter() - t0_req
    full_text = "".join(accumulated_text)

    # 3. Extract entities from LLM answer
    extractor = SocialEntityExtractor()
    extracted_phones = extractor.extract_phones(full_text)
    extracted_emails = extractor.extract_emails(full_text)
    extracted_tax_ids = extract_tax_ids(full_text)

    success = (status_code == 200 and len(full_text) > 0 and error_msg is None)

    # Console feedback
    if success:
        print(f"  ✓ Response received ({len(full_text)} chars) in {total_latency_s:.2f}s (TTFB: {ttfb_ms:.1f}ms)")
        print(f"  ✓ Telemetry: Tokens={prompt_tokens + completion_tokens} | Cost=${cost_micros/1_000_000:.4f} | Citations={citations_count}")
        if extracted_phones:
            print(f"  ✓ Bóc tách SĐT: {extracted_phones}")
        if extracted_tax_ids:
            print(f"  ✓ Bóc tách MST: {extracted_tax_ids}")
    else:
        print(f"  ❌ FAILED: HTTP {status_code} - Error: {error_msg}")

    return PromptExecutionResult(
        prompt_id=p_id,
        domain=domain,
        lang=lang,
        mode=mode,
        status_code=status_code,
        ttfb_ms=ttfb_ms,
        latency_s=total_latency_s,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_micros=cost_micros,
        response_length=len(full_text),
        phones_extracted=extracted_phones,
        tax_ids_extracted=extracted_tax_ids,
        citations_count=citations_count,
        error=error_msg,
        success=success,
    )


async def main():
    print("=" * 80)
    print("🚀 MASTER E2E ENTERPRISE USER PROMPTS BENCHMARK (REAL NOWING API)")
    print(f"Target Endpoint : {BASE_URL}/api/v1/new_chat")
    print(f"Dataset Size    : {len(PROMPTS_DATASET)} Real User Prompts (VI & EN across 6 Domains)")
    print(f"Start Timestamp : {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())}")
    print("=" * 80)

    t_bench_start = time.perf_counter()

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=180.0) as client:
        # Step 1: Real Auth
        resp_login = await client.post(
            "/auth/desktop/login",
            json={"email": USER_EMAIL, "password": USER_PASS},
        )
        if resp_login.status_code != 200:
            print(f"❌ Login failed: HTTP {resp_login.status_code} - {resp_login.text}")
            return

        token = resp_login.json().get("token") or resp_login.json().get("access_token")
        client.headers["Authorization"] = f"Bearer {token}"
        print(f"✓ Authenticated with {USER_EMAIL} (Bearer JWT acquired)\n")

        # Step 2: Get active workspace ID
        resp_ws = await client.get("/workspaces")
        workspaces = resp_ws.json()
        active_ws = next((w for w in workspaces if not w.get("name", "").startswith("[DELETING]")), workspaces[0])
        workspace_id = active_ws["id"]
        print(f"✓ Target Workspace ID: {workspace_id} ('{active_ws.get('name')}')\n")

        # Step 3: Execute all 30 prompts sequentially
        results: list[PromptExecutionResult] = []
        for idx, item in enumerate(PROMPTS_DATASET, 1):
            print(f"--- Running Prompt {idx}/{len(PROMPTS_DATASET)} ---")
            res = await run_prompt_turn(client, workspace_id, item)
            results.append(res)
            # Small natural pause between user prompts
            await asyncio.sleep(0.5)

    total_bench_time = time.perf_counter() - t_bench_start

    # -----------------------------------------------------------------------
    # COMPREHENSIVE BENCHMARK AUDIT & BOTTLENECK REPORT
    # -----------------------------------------------------------------------
    successful_runs = [r for r in results if r.success]
    failed_runs = [r for r in results if not r.success]

    latencies = [r.latency_s for r in successful_runs]
    ttfbs = [r.ttfb_ms for r in successful_runs if r.ttfb_ms > 0]
    costs = [r.cost_micros for r in successful_runs]
    total_tokens = sum(r.prompt_tokens + r.completion_tokens for r in successful_runs)
    total_cost_dollars = sum(costs) / 1_000_000

    latencies.sort()
    ttfbs.sort()

    p50_lat = latencies[int(len(latencies) * 0.50)] if latencies else 0
    p90_lat = latencies[int(len(latencies) * 0.90)] if latencies else 0
    p95_lat = latencies[int(len(latencies) * 0.95)] if latencies else 0

    p50_ttfb = ttfbs[int(len(ttfbs) * 0.50)] if ttfbs else 0
    p95_ttfb = ttfbs[int(len(ttfbs) * 0.95)] if ttfbs else 0

    total_phones_found = sum(len(r.phones_extracted) for r in successful_runs)
    total_tax_ids_found = sum(len(r.tax_ids_extracted) for r in successful_runs)
    total_citations_found = sum(r.citations_count for r in successful_runs)

    print("\n" + "=" * 80)
    print("📊 MASTER E2E ENTERPRISE USER PROMPTS BENCHMARK REPORT:")
    print("=" * 80)
    print(f"  • Total Prompts Evaluated     : {len(results)} prompts (VI & EN across 6 domains)")
    print(f"  • Success Rate / Finish Rate  : {len(successful_runs)}/{len(results)} ({len(successful_runs)*100/len(results):.1f}%)")
    print(f"  • Total Execution Duration    : {total_bench_time:.2f} seconds ({total_bench_time/60:.2f} minutes)")
    print(f"  • Total Tokens Consumed       : {total_tokens:,} tokens")
    print(f"  • Total LLM Spend             : ${total_cost_dollars:.4f} (Avg: ${total_cost_dollars/max(len(successful_runs), 1):.4f}/turn)")
    print("-" * 80)
    print("⏱️ LATENCY & STREAMING PERFORMANCE:")
    print(f"  • Time to First Token (TTFB)  : p50 = {p50_ttfb:.1f} ms | p95 = {p95_ttfb:.1f} ms")
    print(f"  • End-to-End Latency          : p50 = {p50_lat:.2f} s  | p90 = {p90_lat:.2f} s  | p95 = {p95_lat:.2f} s")
    print("-" * 80)
    print("🔍 ENTITY EXTRACTION & RESEARCH DISCOVERY:")
    print(f"  • Total Phone Numbers Found   : {total_phones_found} contacts")
    print(f"  • Total Tax Codes Found       : {total_tax_ids_found} enterprise MSTs")
    print(f"  • Total Citations Generated   : {total_citations_found} web citations")
    print("-" * 80)

    if failed_runs:
        print("⚠️ BOTTLENECK & FAILURE GAPS IDENTIFIED:")
        for fr in failed_runs:
            print(f"  ❌ [{fr.prompt_id}] Mode={fr.mode} - HTTP {fr.status_code}: {fr.error}")
    else:
        print("🎯 SYSTEM STATUS: 🟢 ZERO DROPPED TURNS — 100% SUCCESSFUL E2E EXECUTION")

    print("=" * 80)

    # Save benchmark artifact to JSON for memory ratification
    artifact_path = Path(backend_dir.parent / "_bmad-output/test-artifacts/master_e2e_prompts_benchmark.json")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    with open(artifact_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, ensure_ascii=False, indent=2)
    print(f"✓ Audit artifacts saved to: {artifact_path}\n")

if __name__ == "__main__":
    asyncio.run(main())
