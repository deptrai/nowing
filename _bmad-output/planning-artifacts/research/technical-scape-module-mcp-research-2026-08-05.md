---
stepsCompleted:
  - step-01-init
  - step-02-technical-overview
  - step-03-implementation-approaches
  - step-04-integration-patterns
  - step-05-performance-considerations
  - step-06-final-recommendation
inputDocuments:
  - /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/mcp_tools.py
  - /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/core/store.py
  - /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/core/types.py
  - /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/batdongsan/scrape/definition.py
  - /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/tool.py
  - /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/mcp_oauth/registry.py
  - /Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/routes/workspaces_routes.py
workflowType: research
lastStep: 6
research_type: technical
research_topic: Kiến trúc module ráp vào cho scape tools trong Nowing — MCP, in-process, và hybrid
date: 2026-08-05
web_research_enabled: true
source_verification: true
---

# Research Report: Kiến trúc module ráp vào cho scape tools trong Nowing

**Date:** 2026-08-05
**Author:** Luisphan
**Research Type:** Technical

---

## 1. Research Overview

### 1.1. Research Topic

Tìm kiếm giải pháp kiến trúc phù hợp nhất để Nowing hỗ trợ **scape tools dạng module ráp vào**:

- Các đội dev khác nhau có thể phát triển scraper module độc lập.
- Mỗi user/workspace chỉ thấy và dùng những module mình cần.
- Cân nhắc giữa **in-process capability**, **MCP server riêng**, và **hybrid**.

### 1.2. Research Goals

1. Đánh giá các xu hướng mới nhất 2025–2026 về plugin/module architecture và MCP.
2. Tìm các mẫu kiến trúc multi-tenant cho tool discovery, allowlist, billing.
3. Xác định giải pháp tối ưu cho Nowing dựa trên codebase hiện tại.

### 1.3. Methodology

- Web search trên các nguồn chính thống (MCP spec, blog, GitHub, research blogs).
- Phân tích so sánh trade-offs qua 4 lựa chọn kiến trúc.
- Ánh xạ kết quả về codebase Nowing hiện tại.

---

## 2. Key Findings from Web Research

### 2.1. MCP đã trở thành infrastructure, không còn là dev experiment

Theo nghiên cứu Zylos (2026-03-26):

> MCP, A2A, and ACP now sit under Linux Foundation oversight. The two-layer stack — **MCP for vertical tool integration, A2A for horizontal agent coordination** — is rapidly becoming the architectural default for enterprise agent deployments.

MCP hiện là lựa chọn mặc định cho **agent → tool**, trong khi A2A dành cho **agent → agent**. Với scape tools, MCP là hướng đi đúng.

### 2.2. MCP 2026-07-28 stateless — game changer cho remote MCP servers

Bản release candidate 2026-07-28 có các thay đổi quan trọng:

- **Stateless core**: mỗi request mang protocol version + capabilities trong `_meta`; không cần session sticky, shared session store.
- **`server/discover`**: client có thể lấy capabilities trước khi gọi, thay thế handshake `initialize`.
- **`Mcp-Method` / `Mcp-Name` headers**: gateway có thể route mà không cần parse body.
- **`ttlMs` / `cacheScope`**: client biết cache `tools/list` bao lâu, giảm số lần discovery.
- **OpenTelemetry trace context**: trace theo dõi xuyên suốt từ host → client → MCP server → downstream.

Ý nghĩa thực tiễn: một remote MCP server giờ có thể chạy sau plain round-robin load balancer như một REST API thông thường. Điều này giảm đáng kể operational overhead khi chuyển scape tool ra ngoài.

### 2.3. Multi-tenant MCP gateway đã có nhiều implementation pattern

| Dự án | Đóng góp chính |
|---|---|
| `reaatech/mcp-gateway` | OAuth/API key auth, per-tenant rate limit, schema validation, tool allowlists, fan-out, audit, cache |
| `reaatech/multi-tenant-mcp` | Middleware tách tenant resolution, rate limit, tool visibility, cost accounting, artifact isolation |
| `mcp-hangar` | `server/discover` trả về tenant-scoped tool list từ projection model |
| `kuadrant/mcp-gateway` | Filter `tools/list` theo signed `x-mcp-authorized` JWT chứa `allowed-capabilities` |
| `niradler/fast-mcp-gateway` | Namespace proxying, group-scoped endpoints, `search_tools`/`describe_tool` meta-tools |
| `omer-ayhan/mcpmux` | Multiplexer 1→n upstream, giảm 97% tool-context tokens bằng on-demand discovery |
| `thiagomendes/mcpx` | Self-hosted gateway với virtual gateways, tool governance, multi-tenant isolation |

Pattern chung:

1. Tenant identity được inject tại connection layer (JWT, API key, header).
2. Mỗi tenant chỉ thấy tool manifest của riêng mình (`tools/list` filtered).
3. Tool call được kiểm tra allowlist + rate limit + quota.
4. Audit log và cost accounting gắn với tenant.

Đây chính là câu trả lời cho yêu cầu “không phải user nào cũng cần toàn bộ scape tools” — không cần gán từng user vào từng MCP server, mà dùng một gateway lọc surface theo tenant.

### 2.4. OpenAPI → MCP gateway — lựa chọn thay thế khi scraper đã có REST API

Nếu một team phát triển scraper dưới dạng REST API (FastAPI, NestJS, Go…), có thể đưa vào Nowing qua OpenAPI-to-MCP gateway mà không viết MCP server từ đầu:

- `nathangrove/openapi-mcp-gateway`
- `PivotalServicesOss/openapi-to-mcp`
- `volkan-m/api-to-mcp-gateway`
- `kriptoburak/openapi-mcp-gateway` (multi-spec, multi-auth, FastAPI-native `@mcp_tool`)

Điều này giảm friction cho đội dev khác: họ chỉ cần viết API thông thường + OpenAPI spec, gateway sẽ publish thành MCP tools.

### 2.5. Pluggable scraper frameworks — các mẫu thiết kế tốt

Các framework scraping hiện đại đều chia module theo pipeline:

| Framework | Pattern chính |
|---|---|
| **Prysm** | Puppeteer + pluggable extractors, pagination strategies, content processors |
| **web-scrapers-js** | Crawlee/Playwright + DI-based parser system, Zod validation, queue management |
| **DataScrapexter** | Tiered `FetcherFactory` (static/dynamic/browser/enterprise) + middleware chain |
| **Scrapling** | Fetcher → Engine (curl_cffi/Playwright) → Response/Selector |
| **Scrapit** | YAML-driven declarative configs, multi-backend, transform pipeline |

Mẫu rút ra:

- **Fetch → Bypass → Extract → Normalize → Format** là pipeline chuẩn.
- **Factory + strategy** giúp chọn engine theo tier/trang.
- **Schema-driven input/output** (YAML/JSON/Zod) giúp team độc lập.
- **Plugin registry + auto-discovery** giúp “ráp vào” mà không sửa core.

### 2.6. Billing cho MCP tools — chưa có chuẩn universal nhưng đang hình thành

Theo UsageBox (2026) và TombStoneDash/mcp-billing-spec:

- Meter event ghi lại `tool_id`, `agent_id`, `cost_microcents`, `duration_ms`, `input/output_tokens`.
- Receipt schema HMAC-signed để chứng minh call đã xảy ra.
- Pricing declaration per tool: `per_call | per_token | free`, free tier.

Nowing đã có `BillingUnit` + `cost_micros` trong `ScrapeOutput`, nên billing in-process khá vững. Nếu chuyển ra MCP, cần yêu cầu external MCP server trả về `cost_micros` trong output hoặc Nowing ước tính từ input.

---

## 3. Codebase Nowing Hiện Tại

Nowing đã có sẵn các thành phần quan trọng:

### 3.1. In-process capability registry

- `app/capabilities/core/store.py`: `_REGISTRY` lưu `Capability`.
- `app/capabilities/core/types.py`: `Capability` contract với `name`, `input/output schema`, `executor`, `billing_unit`.
- `app/capabilities/*/scrape/definition.py`: đăng ký scraper capability.

Ví dụ `batdongsan.scrape`:

```python
BATDONGSAN_SCRAPE = Capability(
    name="batdongsan.scrape",
    description="...",
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(web_fetch_fn=fetch_web_listings),
    billing_unit=BillingUnit.BATDONGSAN_ITEM,
)
register_capability(BATDONGSAN_SCRAPE)
```

### 3.2. Built-in MCP tool catalog

- `app/mcp_tools.py`: `MCP_TOOL_CATALOG` với `group=SCRAPER` chứa ~20 scraper tools.
- `app/agents/chat/multi_agent_chat/shared/tools/mcp/tool.py`: MCP client hỗ trợ `stdio`, `streamable-http`, generic `MCP_CONNECTOR`.
- `app/services/mcp_oauth/registry.py`: hardcoded registry cho Linear, Jira, Slack, Notion, …
- `workspace_mcp_tool_settings` (DB): per-workspace bật/tắt built-in MCP tools.

### 3.3. Cái còn thiếu

- Chưa có **centralized module registry** cho scape tools.
- Chưa có **per-tenant tool projection** cho external modules.
- Chưa có **standard contract** cho module phát triển bởi team khác.
- Built-in catalog là static, cần redeploy để thêm tool mới.

---

## 4. Architecture Options

### 4.1. Option A: Giữ nguyên in-process (current)

**Mô tả:** Mọi scraper là Python package dưới `app/capabilities/` và `app/proprietary/platforms/`, đăng ký vào `Capability` registry, expose qua `MCP_TOOL_CATALOG`.

**Pros:**
- Latency thấp nhất.
- Billing (`cost_micros`, `BillingUnit`) kiểm soát chính xác.
- Một codebase, một deploy, test dễ.
- Shared infra: queue, cache, DB, proxy.

**Cons:**
- Team khác phải merge code vào repo Nowing → review bottleneck.
- Mỗi user/workspace phải tải toàn bộ catalog dù không dùng hết (prompt bloat).
- Không thể chạy module bằng ngôn ngữ/runtime khác.

**Verdict:** Tốt cho core, không tốt cho ecosystem mở.

### 4.2. Option B: Chuyển toàn bộ scraper thành MCP server riêng

**Mô tả:** Mỗi scraper chạy như một MCP server độc lập (stdio hoặc HTTP). Nowing kết nối qua `MCP_CONNECTOR`.

**Pros:**
- Team phát triển hoàn toàn độc lập.
- Ngôn ngữ/runtime tùy chọn.
- Per-user/per-workspace dễ dàng qua connector.

**Cons:**
- Network hop mỗi lần scrape → latency + failure modes.
- Operational sprawl: nhiều server, secret, scaling, monitoring.
- Billing khó khớp: MCP server không tự trả về `cost_micros` theo `BillingUnit` của Nowing.
- `tools/list` dài → prompt context bloat (ví dụ 20 scraper × 1–2k tokens).
- Schema drift, version mismatch.

**Verdict:** Quá nặng nếu áp dụng toàn bộ. Phù hợp cho niche/experimental modules.

### 4.3. Option C: Hybrid — Core in-process + Plugin layer qua MCP Gateway + Registry (RECOMMENDED)

**Mô tả:**

- **Core scrapers** (batdongsan, chotot, muaban_bds, youtube, tiktok, reddit, instagram, google_maps, amazon, google_search) giữ in-process, đăng ký như native modules.
- **Plugin scrapers** do đội khác phát triển chạy trong **Scape Module Host** (có thể là một MCP server cho mỗi team hoặc một gateway tổng hợp nhiều module).
- **Scape Module Registry** lưu metadata, schema, version, billing unit, tenant mapping.
- **MCP Gateway** xử lý discovery, tenant context, allowlist, rate limit, audit, fan-out đến các module host.
- Nowing backend chỉ cần nói chuyện với gateway duy nhất; gateway loại bỏ tool mà tenant không được phép.

**Pros:**
- Giữ performance + billing accuracy cho core.
- Cho phép team bên ngoài phát triển module độc lập.
- Per-tenant surface giảm context bloat.
- Có thể cache `tools/list` theo `ttlMs` (MCP 2026-07-28).
- Stateless HTTP giúp scale gateway/module host như REST API.

**Cons:**
- Thêm một lớp gateway cần operate.
- Cần define strict module contract.
- Plugin module phải trả về output shape tương thích (`items`, `cost_micros`, `degraded`, `degradation_reason`).

**Verdict:** Cân bằng tốt nhất giữa autonomy, performance, multi-tenancy.

### 4.4. Option D: OpenAPI-to-MCP bridge cho scraper REST API

**Mô tả:** Các đội dev viết scraper dưới dạng REST API/OpenAPI; Nowing dùng OpenAPI-to-MCP gateway để expose thành MCP tools.

**Pros:**
- Không bắt buộc team học MCP SDK.
- Reuse infra REST hiện có.
- Auto-generate tool schemas từ OpenAPI.

**Cons:**
- Khó áp dụng billing/cost micros tự động.
- Khó kiểm soát `degraded`, `degradation_reason`, `progress`.
- OpenAPI spec thường không tối ưu cho LLM tool use.

**Verdict:** Dùng như một onboarding path cho team mới, nhưng không nên là default cho scape tools chuyên sâu.

---

## 5. Recommended Architecture

### 5.1. Conceptual Design

```
┌─────────────────────────────────────────────────────────────┐
│                      Nowing Backend                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │        Scape Module Registry & Gateway Client       │    │
│  │  - native modules (in-process)                      │    │
│  │  - external modules via MCP gateway                 │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                   │
│  ┌──────────────────────┴──────────────────────────────┐    │
│  │      MCP Gateway (stateless HTTP / stdio)           │    │
│  │  - tenant resolution                                │    │
│  │  - per-tenant allowlist                             │    │
│  │  - rate limit / quota                               │    │
│  │  - tool discovery cache                             │    │
│  └──────────────────────┬──────────────────────────────┘    │
└─────────────────────────┼───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
  Native Modules    Team A Host        Team B Host
 (in-process)     (MCP server)       (MCP server)
 batdongsan        vietnam-bds-2      experimental
 chotot            (FastMCP/Python)   scraper
 ...
```

### 5.2. Component Details

#### A. `ScapeModule` contract

Mở rộng `Capability` hiện tại với thêm metadata:

```python
@dataclass(frozen=True)
class ScapeModule:
    name: str
    version: str
    description: str
    provider: str          # team/org sở hữu
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    executor: Executor | None  # None nếu external
    billing_unit: BillingUnit | None
    deployment_mode: Literal["native", "mcp"]
    mcp_endpoint: str | None
    auth_type: Literal["none", "api_key", "oauth", "platform_account"]
    tags: list[str]
    docs_url: str | None
    trust_level: Literal["built-in", "verified", "community"] = "community"
```

Output schema external module **bắt buộc** trả về:

```python
class ScapeOutput(BaseModel):
    items: list[dict[str, Any]]
    total_items: int
    cost_micros: int
    degraded: bool
    degradation_reason: str | None
    billable_units: int
```

#### B. Scape Module Registry

Lưu trữ trong database hoặc một config service:

- `scape_module_definitions`: metadata, schema hash, version.
- `workspace_scape_module_settings`: which module is enabled for which workspace.
- `workspace_scape_module_tool_settings`: per-tool enable (mở rộng `workspace_mcp_tool_settings` hiện tại).
- `scape_module_connectors`: mapping từ external module instance đến `MCP_CONNECTOR` row.

#### C. MCP Gateway

Có thể dùng một trong hai hướng:

1. **Tự xây lightweight gateway trong Nowing**:
   - Reuse `app/agents/chat/multi_agent_chat/shared/tools/mcp/tool.py`.
   - Thêm tenant resolver, allowlist middleware, rate limit.
   - Cache `tools/list` với `ttlMs`.

2. **Dùng open-source gateway** (`reaatech/mcp-gateway`, `mcpx`, `mcpmux`) nếu muốn outsource governance.

Khuyến nghị: **tự xây** để giữ control billing, HITL, auth model của Nowing.

#### D. Native vs External Split

**Native (in-process):**

- Top 5–10 scraper theo usage.
- Cần billing chính xác, low latency.
- Core team maintain.

**External (MCP):**

- Scrapers theo vertical/region mới.
- Prototype/experimental.
- Modules từ đối tác bên ngoài.
- Modules cần runtime khác (ví dụ Go/Rust cho anti-bot).

### 5.3. Per-User / Per-Workspace Enablement

Tận dụng `workspace_mcp_tool_settings` hiện tại và mở rộng:

```sql
-- mở rộng bảng hiện tại hoặc tách riêng
workspace_scape_module_tool_settings (
    workspace_id,
    module_name,
    tool_name,
    enabled,
    provider,
    trust_level
)
```

Khi main agent build tool list:

1. Lấy native modules từ `Capability` registry.
2. Lấy external modules qua gateway `server/discover` hoặc cached `tools/list`.
3. Lọc theo workspace allowlist.
4. Chỉ đưa vào prompt tools `enabled = true`.

Điều này giải quyết “không phải user nào cũng cần toàn bộ scape tools” — mỗi workspace/user thấy một subset.

### 5.4. Billing & Cost Accounting

Với native: giữ nguyên `BillingUnit` + `cost_micros` trong `ScrapeOutput`.

Với external MCP:

- MCP server **tự tính `cost_micros`** dựa trên output items và trả về.
- Hoặc Nowing ước tính từ `input.estimated_units`.
- Lưu usage event với `idempotencyKey` (tránh double-charge khi retry).

### 5.5. Deployment Model cho Team Dev

**Path 1 — Native Python module (nếu được merge vào Nowing):**

```
nowing-scape-<name>/
  __init__.py
  schemas.py
  executor.py
  definition.py
  tests/
```

**Path 2 — MCP server độc lập (nếu team muốn tự operate):**

```
scape-<team>-host/
  pyproject.toml
  src/
    server.py            # FastMCP/FastAPI app
    modules/
      batdongsan_v2.py
      experimental_x.py
  Dockerfile
  README.md
```

Nowing thêm connector `MCP_CONNECTOR` trỏ đến URL host.

**Path 3 — OpenAPI bridge (nếu team chỉ có REST API):**

- Dùng `openapi-to-mcp` gateway.
- Add spec vào registry.
- Hạn chế: billing/progress khó integrate.

---

## 6. Trade-off Summary

| Dimension | A. Native in-process | B. All MCP | C. Hybrid (Recommended) | D. OpenAPI bridge |
|---|---|---|---|---|
| Latency | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ |
| Billing accuracy | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ |
| Developer autonomy | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Operational complexity | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| Multi-tenant selectivity | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Language/runtime flexibility | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Context window bloat | ⭐ | ⭐ | ⭐⭐⭐ | ⭐ |
| Schema/billing control | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ |

---

## 7. Implementation Roadmap

### Phase 1 — Foundation (1–2 sprints)

1. Chuẩn hóa `ScapeModule` contract mở rộng `Capability`.
2. Tạo `scape_module_registry` table + migration.
3. Refactor `app/mcp_tools.py` catalog để load từ registry thay vì hardcoded.
4. Mở rộng `workspace_mcp_tool_settings` hỗ trợ external modules.

### Phase 2 — MCP Gateway (2–3 sprints)

1. Xây lightweight MCP gateway trong Nowing hoặc chọn open-source.
2. Thêm tenant resolution, allowlist, rate limit.
3. Cache `tools/list` với `ttlMs` từ MCP 2026-07-28.
4. Tích hợp gateway vào `shared/tools/mcp/tool.py`.

### Phase 3 — Team Onboarding (ongoing)

1. Release `nowing-scape-sdk` (template FastMCP + manifest).
2. Viết docs + example cho team phát triển.
3. Hỗ trợ OpenAPI bridge cho team chỉ có REST API.
4. Marketplace/registry UI trong admin dashboard.

---

## 8. Final Recommendation

**Không chuyển toàn bộ scraper thành MCP server riêng.** Cách làm đúng là **hybrid — core in-process + external pluggable modules qua MCP gateway/registry**.

Lý do chính:

- MCP 2026-07-28 stateless làm remote MCP server dễ scale, nhưng không miễn phí operational overhead.
- Billing/progress/degradation của Nowing đã rất vững trong in-process `Capability` framework.
- Multi-tenancy và per-user selectivity giải quyết tốt hơn ở **gateway/registry layer** hơn là chia nhỏ từng scraper thành server riêng.
- Các đội dev có thể phát triển theo 3 path: native module, MCP server, hoặc OpenAPI bridge.

Cách tiếp cận này vừa bảo vệ core business (low latency, billing chính xác), vừa mở cửa ecosystem (team ngoài, ngôn ngữ khác, deploy độc lập), vừa giữ “không phải user nào cũng cần toàn bộ scape tools” nhờ per-tenant projection.

---

## 9. Sources

1. Model Context Protocol Specification 2026-07-28 — Architecture. https://modelcontextprotocol.io/specification/2026-07-28/architecture
2. The 2026-07-28 MCP Specification Release Candidate — Model Context Protocol Blog. https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/
3. Zylos Research — Agent Interoperability Protocols 2026: MCP, A2A, ACP and the Path to Convergence. https://zylos.ai/research/2026-03-26-agent-interoperability-protocols-mcp-a2a-acp-convergence/
4. reaatech/mcp-gateway — Production MCP gateway. https://github.com/reaatech/mcp-gateway
5. reaatech/multi-tenant-mcp — Multi-tenancy primitives for MCP. https://github.com/reaatech/multi-tenant-mcp
6. omer-ayhan/mcpmux — Dynamic MCP multiplexer. https://github.com/omer-ayhan/mcpmux
7. thiagomendes/mcpx — Self-hosted MCP gateway. https://github.com/thiagomendes/mcpx
8. kuadrant/mcp-gateway — User-based tool filter. https://github.com/kuadrant/mcp-gateway
9. stacklok/toolhive-registry-server — MCP registry server. https://github.com/stacklok/toolhive-registry-server
10. winsenlabs/platos — Tool gateway, multi-tenant, externally-registered services. https://github.com/winsenlabs/platos
11. TrueFoundry — Building a Centralized MCP Registry. https://www.truefoundry.com/blog/centralized-mcp-registry-architecture
12. PivotalServicesOss/openapi-to-mcp — Convert OpenAPI to MCP. https://github.com/PivotalServicesOss/openapi-to-mcp
13. nathangrove/openapi-mcp-gateway — OpenAPI/Swagger to MCP. https://github.com/nathangrove/openapi-mcp-gateway
14. kriptoburak/openapi-mcp-gateway — FastAPI-native multi-spec MCP. https://github.com/kriptoburak/openapi-mcp-gateway
15. UsageBox — How to Charge for an MCP Server in 2026. https://usagebox.com/articles/how-to-charge-for-mcp-server-2026-per-call-subscription-x402
16. TombStoneDash/mcp-billing-spec — Open standard for MCP billing. https://github.com/TombStoneDash/mcp-billing-spec
17. pinkpixel-dev/prysm — Pluggable Puppeteer scraper. https://github.com/pinkpixel-dev/prysm
18. tsrdatatech/web-scrapers-js — Pluggable parser architecture. https://github.com/tsrdatatech/web-scrapers-js
19. DataScrapexter — Production Go scraping framework. https://valpere.github.io/blog/2026/04/01/datascrapexter-architecture/
20. Scrapling — Modular fetcher/parser architecture. https://d4vinci-scrapling.mintlify.app/concepts/architecture
