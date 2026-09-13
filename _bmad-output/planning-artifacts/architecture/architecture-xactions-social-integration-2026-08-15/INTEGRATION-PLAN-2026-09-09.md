# Kế Hoạch Tích Hợp Toàn Diện XActions (v3.5.0 mới nhất) vào Nowing

**Ngày:** 2026-09-09  
**Tác giả:** Winston (BMAD System Architect)  
**Trạng thái:** Đề xuất thực thi — phương án A: MCP streamable-http (đã được phê duyệt)  
**Scope:** Bao gồm toàn bộ XActions MCP/HTTP, Redis Stream, multi-domain crawlers (Ecom, BĐS, Tuyển dụng, B2B), governance, và alert hooks.

---

## 1. Quyết Định Kiến Trúc

### Phương án được chọn: **A — MCP streamable-http**

**Lý do:**

- Nowing **đã có hạ tầng MCPClient** trong `app/agents/chat/multi_agent_chat/shared/tools/mcp/client.py`, hỗ trợ cả `stdio_client` và `streamablehttp_client`.
- Nowing **đã dùng MCP cho các third-party khác**: Exa (`https://mcp.exa.ai/mcp`), Notion, Confluence, Slack, Linear, Jira, Airtable, Discord, Luma — tất cả đều qua `mcp_oauth/registry.py`.
- XActions đã đầu tư sâu vào MCP layer: Bearer auth, `X-Consumer-Id` quota, `AdaptiveRateGovernor`, tool discovery (`x_actions_list`, `x_schema_list/get`), admin hooks (`x_admin_*`).
- So với stdio subprocess hiện tại, `streamablehttp_client` loại bỏ hoàn toàn việc spawn `node src/mcp/server.js` mỗi lần gọi, tái sử dụng HTTP connection pool, giảm latency từ giây xuống ~10-50ms sau initialize.

**Không dùng REST vì:**

- `/api/platform/:platform/scrape` yêu cầu JWT user auth, không phù hợp service-to-service.
- REST API của XActions chưa có consumer quota, governor hook, hay Redis stream publisher tích hợp — cần XActions code thêm nhiều.
- MCP là hợp đồng đã chốt trong `PRD-ECOSYSTEM-TRINITY-ALIGNMENT.md` (Luồng C).

### Nhược điểm MCP cần giải quyết

- Dữ liệu lớn bị giới hạn preview 30 records (3-Layer Envelope), trên 100 records sẽ export artifact. Nowing cần xử lý artifact hoặc dùng Redis Stream để nhận thin events.
- Session state cần quản lý đúng (không tạo session mỗi lần gọi, không bị memory leak).

---

## 2. Trạng Thái Thực Tế (Audit 2026-09-09)

| Thành phần | Trạng thái XActions | Trạng thái Nowing | Ghi chú |
|---|---|---|---|
| MCP HTTP daemon (`MCP_TRANSPORT=http PORT=3001`) | ✅ Sẵn có, StreamableHTTP | ❌ Nowing dùng stdio | `src/mcp/server.js` line 5820 |
| Bearer auth + consumer quota (`X-Consumer-Id: nowing`) | ✅ `consumer-context.js` + `adaptive-governor.js` | ❌ Chưa cấu hình | XActions mặc định `nowing` RPM 60, burst 15 |
| Redis Stream publisher `stream:social:raw_posts` | ✅ `RedisStreamPublisher` + Facebook crawler xAdd | ⚠️ Nowing adapter xAdd từ Python | Có 2 nguồn ghi stream, consumer Nowing phải đọc được cả 2 |
| Adaptive Rate Governor | ✅ Healthy proxy scaling, hibernation, lag ×0.25 | ❌ Chưa đọc governor status | `src/core/adaptive-governor.js` |
| Multi-domain `scrape(platform, action, options)` | ✅ Dispatcher sẵn | ❌ Chưa gọi | `src/scrapers/index.js` |
| MCP tool cho VN crawlers (chotot, shopee, topcv...) | ⚠️ Chỉ `x_crawl_post` / `x_crawl_comments_tree` chung | — | Cần XActions expose rõ hoặc tool `x_scrape` |
| Nowing stream consumer Celery wiring | — | ❌ Không có caller | `social_stream_worker.py` line 500, only tests import |
| `XActionsSocialAdapter` | — | ⚠️ Chỉ 2 tool, stdio, global FB cookie | `nowing_backend/app/proprietary/platforms/xactions/adapter.py` |
| Social routes CRUD | — | ⚠️ Chỉ POST, platform enum hẹp | `social_routes.py` |

---

## 3. Phân Chia Trách Nhiệm

### 3.1 Team XActions (có thể yêu cầu code thêm)

| Công việc | Mức độ | Lý do |
|---|---|---|
| **A1. Expose generic `x_scrape` MCP tool** | Bắt buộc | `scrape(platform, action, args)` trong `src/scrapers/index.js` đã hỗ trợ mọi domain, nhưng MCP không gọi trực tiếp. Cần tool với schema: `{ platform: string, action: string, args: object, accountId?: string, proxyUrl?: string }`. |
| **A2. Đảm bảo thin event stream từ mọi crawler** | Bắt buộc | Hiện chỉ thấy Facebook crawler xAdd. Các crawler khác cần dùng `RedisStreamPublisher` khi `REDIS_STREAM_ENABLED=true`. |
| **A3. Document platform+action matrix** | Bắt buộc | Nowing cần biết chính xác action nào mỗi platform hỗ trợ. |
| **A4. Hỗ trợ per-account `{accountId}` cho Facebook/Twitter** | Khuyến nghị | Thay vì global `c_user/xs`, dùng account pool của XActions qua `x_facebook_list_accounts`. |
| **A5. Expose `x_governor_status` và `x_admin_stream_metrics` ổn định** | Khuyến nghị | Nowing admin dashboard cần. |

### 3.2 Team Nowing

| Công việc | Mức độ | File chính |
|---|---|---|
| **N1. Viết `XActionsMcpClient` dùng `streamablehttp_client`** | Bắt buộc | `app/proprietary/platforms/xactions/adapter.py` hoặc `mcp_client.py` mới |
| **N2. Đăng ký `run_social_stream_consumer` thành Celery task + beat** | Bắt buộc | `app/celery_app.py`, `app/tasks/celery_tasks/social_stream_worker.py` |
| **N3. Mở rộng `SUPPORTED_PLATFORMS` + target enum + routes CRUD** | Bắt buộc | `social_xactions_ingest.py`, `social_routes.py`, `app/db/models/leads/social.py` |
| **N4. Viết `UniversalScrapeTargetMapper`** | Bắt buộc | `app/proprietary/platforms/xactions/mapper.py` mới |
| **N5. Cấu hình `XACTIONS_MCP_URL`, `XACTIONS_MCP_API_KEY`, `XACTIONS_CONSUMER_ID`** | Bắt buộc | `app/config/entities.py`, `.env`, `app/config/__init__.py` |
| **N6. Kết nối health/governor probes** | Khuyến nghị | `app/health/registry.py`, admin telemetry |
| **N7. Xử lý artifact >100 records** | Khuyến nghị | `XActionsMcpClient` detect `datasetArtifactPath` và đọc file |
| **N8. Test shadow-run so sánh dữ liệu cũ/mới** | Khuyến nghị | `tests/integration/platforms/test_social_redis_stream.py` |

---

## 4. Chi Tiết Adapter Mới

### 4.1 Sử dụng `MCPClient` có sẵn

`app/agents/chat/multi_agent_chat/shared/tools/mcp/client.py` đã hỗ trợ:

```python
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

async with (
    streamablehttp_client(url, headers=headers) as (read, write, _),
    ClientSession(read, write) as session,
):
    await session.initialize()
    response = await session.call_tool(name, arguments)
```

Tuy nhiên, MCPClient hiện tại khởi tạo qua `(command, args, env)` — cần mở rộng hoặc tạo lớp con cho HTTP.

### 4.2 `XActionsMcpClient` đề xuất

```python
# app/proprietary/platforms/xactions/mcp_client.py (mới)

from __future__ import annotations

import json
import logging
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.config import config

logger = logging.getLogger(__name__)


class XActionsMcpClient:
    """Persistent StreamableHTTP MCP client for XActions.

    Reuses HTTP connection pool and a single MCP session per lifecycle.
    Uses Bearer auth and X-Consumer-Id headers per AD-20 / Trinity contract.
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        consumer_id: str = "nowing",
    ):
        self.url = (url or config.XACTIONS_MCP_URL or "http://xactions:3001/mcp").rstrip("/")
        self.api_key = api_key or config.XACTIONS_MCP_API_KEY
        self.consumer_id = consumer_id
        self._session: ClientSession | None = None
        self._headers: dict[str, str] = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Consumer-Id": self.consumer_id,
        }

    async def __aenter__(self) -> "XActionsMcpClient":
        self._read, self._write, _ = await streamablehttp_client(
            self.url, headers=self._headers
        ).__aenter__()
        self._session = ClientSession(self._read, self._write)
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session:
            await self._session.__aexit__(exc_type, exc, tb)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self._session:
            raise RuntimeError("MCP session not initialized")

        response = await self._session.call_tool(name, arguments=arguments)

        texts = []
        for content in response.content:
            if hasattr(content, "text"):
                texts.append(content.text)
            elif hasattr(content, "data"):
                texts.append(str(content.data))
            else:
                texts.append(str(content))

        result_text = "\n".join(texts).strip()
        if not result_text:
            return {"success": True, "data": [], "meta": {}}

        try:
            envelope = json.loads(result_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Non-JSON XActions response: {exc}") from exc

        if response.isError:
            return {
                "success": False,
                "error": envelope.get("error", {}).get("message", "unknown"),
                "data": [],
                "meta": envelope.get("meta", {}),
            }

        # Handle artifact for large datasets
        artifact_path = envelope.get("meta", {}).get("datasetArtifactPath")
        if artifact_path:
            # Future: read artifact from XActions shared storage or S3
            logger.info("XActions returned artifact: %s", artifact_path)

        return {
            "success": envelope.get("success", True),
            "data": envelope.get("data", []),
            "meta": envelope.get("meta", {}),
            "summary": envelope.get("summary", {}),
            "artifact_path": artifact_path,
        }
```

### 4.3 Thay thế `XActionsSocialAdapter._call_mcp_tool`

Trong `app/proprietary/platforms/xactions/adapter.py`, thay `stdio_client` bằng:

```python
# Cũ:
async with (
    stdio_client(server=server_params) as (read, write),
    ClientSession(read, write) as session,
):
    ...

# Mới:
from app.proprietary.platforms.xactions.mcp_client import XActionsMcpClient

async with XActionsMcpClient() as client:
    raw = await client.call_tool(tool_name, arguments)
```

Hoặc tốt hơn: lưu `client` trong `XActionsSocialAdapter` và tái sử dụng cho nhiều lần gọi.

---

## 5. Pha Thực Hiện (Ưu Tiên Tốc Độ)

### Phase 0 — Hotfix P0 (1–2 ngày)
**Mục tiêu:** Production không bị tích tụ stream, 2 platform hiện có hoạt động đúng.

- **N2:** Tạo `celery_tasks/social_stream_worker.py` gói `run_social_stream_consumer` thành Celery task `process_social_stream`, chạy mỗi 30 giây hoặc long-running worker.
- **N3 (tối thiểu):** Mở rộng target enum cho `facebook_page` và `twitter_user` (scheduler hiện warning và skip).
- **N5:** Thêm config `XACTIONS_MCP_URL` / `XACTIONS_MCP_API_KEY` / `XACTIONS_CONSUMER_ID`.

### Phase 1 — MCP StreamableHTTP Migration (3–5 ngày)
**Mục tiêu:** Nowing giao tiếp XActions qua `streamablehttp_client`, adapter gọi được bất kỳ platform nào.

- Hoàn thành **A1** của XActions (hoặc dùng `x_crawl_post` tạm nếu A1 chưa xong).
- Viết `XActionsMcpClient` (phần 4.2).
- Cập nhật `_build_mcp_tool_args` để dispatch:
  - Facebook group/page: `x_facebook_group_posts` / `x_facebook_posts`
  - Twitter keyword/user: `x_search_tweets` / `x_get_tweets`
  - Tất cả còn lại: `x_scrape(platform, action, args)` (hoặc `x_crawl_post` tạm)
- Cập nhật `ingest_raw_post_to_stream` để gửi đủ `target_id`, `workspace_id`, `client_id`.

### Phase 2 — Multi-Domain Target Expansion (3–4 ngày)
**Mục tiêu:** Người dùng Nowing có thể tạo target cho Ecom/BĐS/HR/B2B.

- Mở rộng `SocialTargetCreate` enum + DB migration.
- Viết `UniversalScrapeTargetMapper` ánh xạ `target_id` + `platform` thành `args` phù hợp cho XActions.
- Mở rộng `SUPPORTED_PLATFORMS` trong `social_xactions_ingest.py`.
- Cập nhật `SocialEntityExtractor` / `compute_fit_score` cho các intent mới (`hiring`, `seeking`, `bds_sell`, `bds_buy`, `product_listing`).

### Phase 3 — Governance, Health, Artifact Handling (2–3 ngày)
**Mục tiêu:** Production-grade observability, account/proxy health, admin controls.

- Kết nối `x_governor_status` vào `/health` hoặc admin telemetry.
- Tạo Celery task `sync_xactions_proxy_pool` gọi `x_admin_proxies_list`.
- Xử lý `datasetArtifactPath` khi >100 records (đọc từ shared storage hoặc bảo XActions ghi artifact lên S3/Redis).
- Thêm alert khi `x_admin_stream_alerts` báo breach.

### Phase 4 — Shadow-Run & Legacy Decommission (5–7 ngày)
**Mục tiêu:** Xác nhận parity ≥ 99%, xóa scraper cũ Nowing.

- Chạy song song old adapter (nếu còn) và XActions HTTP adapter.
- So sánh output record count, phone/price/location extraction, intent accuracy.
- Sau parity OK: xóa các thư mục scraper legacy trong `nowing_backend/app/proprietary/platforms/` (ngoại trừ `xactions/`).
- Giảm kích thước Dockerfile Nowing (không còn Playwright/Chromium).

---

## 6. Cấu Hình Môi Trường

Thêm vào `.env` / `nowing_backend/.env.local`:

```bash
XACTIONS_MCP_URL=http://xactions:3001/mcp
XACTIONS_MCP_API_KEY=<shared-bearer-token>
XACTIONS_CONSUMER_ID=nowing
# Optional per-account pool (thay thế global FB cookie)
XACTIONS_FACEBOOK_ACCOUNT_ID=<default-account>

# Redis stream (đã có nhưng đảm bảo)
REDIS_APP_URL=redis://redis:6379/0
```

Thêm vào `nowing_backend/app/config/entities.py`:

```python
XACTIONS_MCP_URL: str = "http://xactions:3001/mcp"
XACTIONS_MCP_API_KEY: str | None = None
XACTIONS_CONSUMER_ID: str = "nowing"
XACTIONS_FACEBOOK_ACCOUNT_ID: str | None = None
```

---

## 7. Cập Nhật CSDL

### Migration 1: `social_monitored_targets` mở rộng platform enum
```sql
ALTER TABLE social_monitored_targets
  DROP CONSTRAINT IF EXISTS uq_social_target;

ALTER TABLE social_monitored_targets
  ADD CONSTRAINT uq_social_target UNIQUE (workspace_id, platform, target_id);
```

### Migration 2: `social_posts` thêm `category`, `storage_ref`, `scraper_id`
```sql
ALTER TABLE social_posts
  ADD COLUMN category VARCHAR(50) DEFAULT 'general',
  ADD COLUMN storage_ref TEXT,
  ADD COLUMN scraper_id VARCHAR(100),
  ADD COLUMN benchmark_health VARCHAR(10),
  ADD COLUMN benchmark_alert BOOLEAN DEFAULT FALSE;
```

### Migration 3: `xactions_proxy_bindings` mới
```sql
CREATE TABLE IF NOT EXISTS xactions_proxy_bindings (
    id BIGSERIAL PRIMARY KEY,
    workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    account_id VARCHAR(255) NOT NULL,
    proxy_url TEXT,
    platform VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_bound_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_xactions_proxy_binding UNIQUE (workspace_id, account_id, platform)
);
```

---

## 8. Định Dạng Redis Stream Thin Event

XActions gửi thin event pointer:
```json
{
  "id": "facebook:123456",
  "platform": "facebook",
  "externalId": "123456",
  "category": "bds",
  "authorId": "",
  "crawledAt": "2026-09-09T10:00:00.000Z",
  "storageRef": "facebook:123456",
  "scraperId": "facebook-hybrid",
  "benchmark_health": "A",
  "benchmark_alert": "false"
}
```

Nowing consumer phải **linh hoạt**:
- Nếu event có đầy đủ `content`, xử lý trực tiếp.
- Nếu event là thin pointer, gọi lại XActions `x_crawl_post` để fetch full payload.
- ACK sau khi xử lý thành công, DLQ khi lỗi.

---

## 9. Quy Trình Xử Lý Lỗi và Degradation

| Lỗi từ XActions | Hành động Nowing |
|---|---|
| `XACT_4291` consumer quota exceeded | Retry sau `retryAfter`, giảm frequency scheduler |
| `PROXY_EXHAUSTED` / `XACT_5030` | Tạm dừng target, alert admin, không tự cào nội bộ (AD-SOC-1) |
| `ACCOUNT_HIBERNATION` | Chuyển account khác (nếu có), hoặc dừng 15–30 phút |
| `SIGNER_CRASH` / `XACT_5000` | Retry tối đa 3 lần, sau đó DLQ + Telegram alert |
| `XACT_4010` auth expired | Log fatal, dừng scheduler, yêu cầu cập nhật `XACTIONS_MCP_API_KEY` |
| `datasetArtifactPath` returned | Fetch artifact, merge with preview data |

---

## 10. Kiểm Thử Tối Thiểu

- Unit: `test_xactions_mcp_client.py` — `streamablehttp_client` init, auth headers, session reuse, 401/429 handling.
- Integration: `test_social_redis_stream.py` — produce thin event → consumer persists `SocialPost` + `Lead`.
- Integration: `test_xactions_multi_domain.py` — gọi `x_scrape(platform, action, args)` cho mỗi platform (chotot, shopee, topcv, batdongsan, masothue).
- E2E: Frontend tạo target mới, Celery ingest, stream consumer, lead xuất hiện trong UI.
- Shadow-run: 7 ngày so sánh output XActions vs legacy Nowing scraper.

---

## 11. Rủi Ro và Trade-Off

| Rủi ro | Khắc phục |
|---|---|
| XActions team chậm expose `x_scrape` | Tạm dùng `x_crawl_post` + `x_crawl_comments_tree` cho post detail; search/bulk bị hạn chế |
| Facebook cookie tài khoản bị chặn | Dùng XActions account pool (`x_facebook_list_accounts` + `accountId`) thay vì global cookie |
| Redis stream consumer chưa chạy → tích tụ message | Phase 0 phải hoàn thành trước khi mở rộng platform |
| Dữ liệu lớn bị preview 30 records | Xử lý `datasetArtifactPath` hoặc dùng Redis Stream thin events |
| Nhiều platform cùng lúc gây vượt quota | XActions governor tự throttle, Nowing scheduler frequency adaptive |

---

## 12. Quyết Định Tiếp Theo

1. **Ngay lập tức:** Luis phê duyệt pha thực hiện và ưu tiên Phase 0 + Phase 1.
2. **Yêu cầu team XActions:** Hoàn thành **A1** (expose `x_scrape`) trong 2–3 ngày, hoặc cung cấp danh sách chính xác các action hỗ trợ per platform.
3. **Team Nowing:** Bắt đầu viết `XActionsMcpClient` dùng `streamablehttp_client` và Celery wiring song song, không chờ A1 hoàn thành.
4. **Họp sync:** 30 phút sau 3 ngày để xác nhận HTTP MCP adapter kết nối được `xactions:3001/mcp` và consumer stream đang chạy.
