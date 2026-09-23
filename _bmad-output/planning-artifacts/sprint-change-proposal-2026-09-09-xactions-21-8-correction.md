# Sprint Change Proposal — Story 21.8 Social Ingress via XActions Integration

**Ngày:** 2026-09-09  
**Tác giả:** Correct Course Workflow  
**Mode:** Batch  
**Trigger:** Kế hoạch tích hợp XActions toàn diện (`INTEGRATION-PLAN-2026-09-09.md`) phát hiện Story 21.8 đang ở trạng thái `done` nhưng có nhiều acceptance criteria chưa thực sự hoàn thành hoặc đã lỗi thời.  
**Tác động chính:** Story 21.8 cần được mở lại, tách thành 2 epic con hoặc 6+ stories mới, cập nhật `epics.md`, `sprint-status.yaml`, `ARCHITECTURE-SPINE.md`, code adapter, routes, Celery wiring.

---

## Section 1 — Issue Summary

### Trigger

Trong quá trình lập kế hoạch tích hợp toàn diện XActions với code mới nhất, phát hiện:

- Story 21.8 đã được đánh dấu `done` trong `sprint-status.yaml` (line 241).
- Tuy nhiên, mã nguồn hiện tại cho thấy nhiều phần chưa hoàn thành hoặc chưa đúng với AC:
  1. `XActionsSocialAdapter` dùng **stdio subprocess** (`node src/mcp/server.js`) mỗi lần gọi, không reuse session — mâu thuẫn với AC yêu cầu "XActions stealth session pool".
  2. `SUPPORTED_PLATFORMS` chỉ có `{facebook_group, twitter_keyword}` — không hỗ trợ Facebook page, Twitter user, TikTok, Chợ Tốt, Shopee, TopCV, VietnamWorks, LinkedIn, Batdongsan, Mã số thuế, v.v. như Architecture Spine AD-SOC-9 quy định.
  3. `run_social_stream_consumer` đã viết xong nhưng **chưa được đăng ký làm Celery task/beat**, nghĩa là Redis Stream `stream:social:raw_posts` tích tụ mãi mãi — P0 production blocker.
  4. Chỉ có endpoint `POST /social-monitored-targets`, thiếu GET/PATCH/DELETE.
  5. Facebook auth dùng **global env cookie** (`XACTIONS_FACEBOOK_C_USER`, `XACTIONS_FACEBOOK_XS`) thay vì per-account từ XActions account pool.
  6. `x_scrape` / `x_crawl_post` cho multi-domain chưa được sử dụng.

### Problem Statement

Story 21.8 được đóng quá sớm. Trạng thái `done` gây hiểu nhầm rằng social ingress đã hoàn chỉnh, trong khi thực tế chỉ mới hoàn thành:
- DB schema (`social_monitored_targets`, `social_posts`)
- Entity extraction (`SocialEntityExtractor`)
- Basic Redis Stream publisher từ Python adapter
- Unit/Integration tests cho regex và Redis Stream

Các khía cạnh quan trọng về **transport**, **session reuse**, **multi-domain expansion**, **consumer wiring**, **governance** chưa xong.

### Evidence

1. `nowing_backend/app/proprietary/platforms/xactions/adapter.py` line 197: comment "ponytail" thừa nhận stdio không reuse session.
2. `nowing_backend/app/tasks/celery_tasks/social_xactions_ingest.py` line 38-39: `SUPPORTED_PLATFORMS = {"facebook_group", "twitter_keyword"}`.
3. `nowing_backend/app/tasks/social_stream_worker.py` line 500: `run_social_stream_consumer` không có production caller.
4. `nowing_backend/app/routes/social_routes.py`: chỉ có `POST`, không có GET/PATCH/DELETE.
5. `nowing_backend/app/celery_app.py` beat schedule: có `check_social_monitored_targets` nhưng không có `process_social_stream`.
6. `_bmad-output/planning-artifacts/architecture/architecture-xactions-social-integration-2026-08-15/ARCHITECTURE-SPINE.md` yêu cầu AD-SOC-4 dual-channel, AD-SOC-9 multi-domain, AD-SOC-11 adaptive rate limiting.

---

## Section 2 — Impact Analysis

### Epic Impact

| Epic | Impact | Action |
|---|---|---|
| **Epic 21: Lead Gen Intelligence** | Trọng tâm | Cần mở lại Story 21.8, thêm stories 21.8a–21.8f |
| **Epic 21.8 Social Ingress** (sub-epic) | Cần tạo hoặc mở rộng | Từ 1 story thành 6 stories cụ thể |
| **Epic 26: Autonomous Lead Missions** | Gián tiếp | DSH Pre-Flight Plan cần social source coverage badges (Story 26.28) phụ thuộc vào multi-domain targets |
| **Epic 29: SaaS Operations & Admin Analytics** | Gián tiếp | Admin telemetry cần `x_governor_status`, `x_admin_stream_metrics` |
| **Epic 10/E12 (VN Scrapers)** | Có thể decommission hoặc redirect | Nếu XActions mở khóa chotot/shopee/topcv/vietnamworks, các scraper legacy trong Nowing có thể xóa |

### Story Impact

Story 21.8 hiện tại không đủ chi tiết để thực thi. Cần tách thành:

1. **Story 21.8a: MCP StreamableHTTP Transport for XActions**
   - Đổi từ stdio subprocess sang `streamablehttp_client`.
   - Thêm `XActionsMcpClient`, config `XACTIONS_MCP_URL`, `XACTIONS_MCP_API_KEY`, `XACTIONS_CONSUMER_ID`.

2. **Story 21.8b: Redis Stream Consumer Celery Wiring**
   - Đăng ký `run_social_stream_consumer` làm Celery task `process_social_stream`.
   - Thêm beat schedule.
   - Xử lý thin events + full content events.

3. **Story 21.8c: Multi-Domain Social Target Expansion**
   - Mở rộng platform enum: `facebook_page`, `twitter_user`, `tiktok_hashtag`, `chotot_category`, `shopee_keyword`, `topcv_search`, `vietnamworks_search`, `linkedin_company`, `batdongsan_category`, `masothue_lookup`, `b2b_registry_search`.
   - Mở rộng routes CRUD.

4. **Story 21.8d: Universal Scrape Target Mapper**
   - Viết `UniversalScrapeTargetMapper` ánh xạ target → XActions tool args.
   - Gọi `x_scrape` / `x_facebook_group_posts` / `x_search_tweets` / `x_get_tweets`.

5. **Story 21.8e: Per-Account Proxy & Cookie Binding**
   - Thay global env cookie bằng per-account `accountId` từ XActions.
   - Proxy binding theo workspace.

6. **Story 21.8f: XActions Governance & Health Integration**
   - Kết nối `x_governor_status`, `x_admin_stream_metrics`, `x_admin_stream_alerts`.
   - Admin telemetry + alert hooks.

### Artifact Conflicts

| Artifact | Tình trạng | Cần cập nhật |
|---|---|---|
| `epics.md` | Story 21.8 text chưa phản ánh stdio/MCP gap | Viết lại AC, thêm 21.8a–f |
| `sprint-status.yaml` | Story 21.8 `done` không chính xác | Đổi thành `in-progress` hoặc `reopened`; thêm 21.8a–f |
| `ARCHITECTURE-SPINE.md` | Đã đúng với AD-SOC-1..11 | Cập nhật phần `XActionsSocialAdapter` note |
| `PRD-ECOSYSTEM-TRINITY-ALIGNMENT.md` | Đã chốt MCP HTTP | Không cần sửa, nhưng cần reference |
| Code: `adapter.py` | Stdio, 2 tool | Refactor theo 21.8a/21.8d |
| Code: `social_xactions_ingest.py` | 2 platform, auth_cookie=None | Refactor theo 21.8c/21.8e |
| Code: `social_stream_worker.py` | Worker hoàn chỉnh nhưng chưa wired | Refactor theo 21.8b |
| Code: `social_routes.py` | Chỉ POST | Refactor theo 21.8c |
| Code: `celery_app.py` | Thiếu stream consumer beat | Thêm `process_social_stream` theo 21.8b |
| Code: `app/config/entities.py` | Thiếu `XACTIONS_MCP_URL` | Thêm theo 21.8a |

### Technical Impact

| Layer | Thay đổi |
|---|---|
| **Adapter** | Từ stdio sang `streamablehttp_client`; session reuse; artifact handling |
| **Celery** | Thêm task `process_social_stream`; beat schedule mới |
| **DB** | Migration mở rộng `platform` enum, thêm `category/storage_ref/scraper_id/benchmark_*` vào `social_posts` |
| **Routes** | Thêm GET/PATCH/DELETE `/social-monitored-targets` |
| **Config** | Thêm `XACTIONS_MCP_URL`, `XACTIONS_MCP_API_KEY`, `XACTIONS_CONSUMER_ID`, `XACTIONS_FACEBOOK_ACCOUNT_ID` |
| **Frontend** | Cần cập nhật dropdown platform nếu mở rộng 10+ platform |
| **Tests** | Unit test `XActionsMcpClient`; integration test multi-domain; shadow-run parity |
| **Infrastructure** | XActions phải chạy với `MCP_TRANSPORT=http PORT=3001`; Redis stream enabled |

### Risk Assessment

| Rủi ro | Mức | Khắc phục |
|---|---|---|
| Story 21.8 đã `done` → mở lại ảnh hưởng velocity metric | Trung bình | Ghi rõ lý do course-correct trong retro; coi đây là follow-up epic, không phải lỗi cá nhân |
| XActions team chậm expose `x_scrape` | Cao | Tạm dùng `x_crawl_post` cho post detail; đẩy search/sang Phase 2 |
| MCP session memory leak | Trung bình | Dùng `asynccontextmanager`, đảm bảo close session; hoặc dùng short-lived pool |
| Stream consumer chạy song song với meta-scheduler gây xung đột | Thấp | Redis lock + consumer group đã có |
| Multi-platform cùng lúc vượt quota | Trung bình | XActions governor tự throttle; Nowing adaptive frequency |

---

## Section 3 — Recommended Approach

### Chọn: **Option 1 — Direct Adjustment** (kết hợp với việc mở rộng scope)

**Lý do:**
- Story 21.8 đã có phần lớn nền tảng (DB schema, extractor, tests). Không cần rollback.
- Vấn đề là scope chưa đủ rộng và implement chưa hoàn thiện. Cách tốt nhất là mở rộng scope, tách thành sub-stories, và tiếp tục.
- Rollback sẽ tốn thời gian và mất công sức đã bỏ ra. MVP review không cần thiết vì business value vẫn rõ ràng.

### Pha thực hiện (đã đề xuất trong `INTEGRATION-PLAN-2026-09-09.md`)

| Phase | Story tương ứng | Thời gian |
|---|---|---|
| **P0 — Hotfix** | 21.8b (stream consumer wiring) + 21.8c tối thiểu (facebook_page, twitter_user) | 1–2 ngày |
| **P1 — MCP Transport** | 21.8a + 21.8d | 3–5 ngày |
| **P2 — Multi-Domain** | 21.8c đầy đủ + 21.8d | 3–4 ngày |
| **P3 — Governance** | 21.8f | 2–3 ngày |
| **P4 — Shadow-Run & Decommission** | 21.8e + cross-cutting | 5–7 ngày |

---

## Section 4 — Detailed Change Proposals

### 4.1 `epics.md` — Story 21.8

**OLD:**

```markdown
### Story 21.8: Social Ingress via XActions Integration

As a B2B sales development representative or real estate investor,
I want to ingest targeted Facebook Group posts and Twitter keyword searches via XActions integration,
So that I can capture real-time social conversations and extract contact numbers without building scrapers from scratch.

**Acceptance Criteria:**
- ...
- **Given** target groups or search keywords, **When** `XActionsSocialAdapter` calls `x_facebook_group_posts` or `x_search_tweets`, **Then** raw social posts are fetched via XActions stealth session pool with sticky 1-to-1 residential proxy IP binding per account.
- ...
```

**NEW:**

```markdown
### Story 21.8: Social Ingress via XActions Integration — Foundation (Baseline)

As a B2B sales development representative or real estate investor,
I want a foundation to ingest social posts via XActions,
So that I can capture real-time conversations and extract contact numbers without building scrapers from scratch.

**Scope (Baseline / Done):**
- PostgreSQL schema `social_monitored_targets` and `social_posts` with unique constraints.
- `SocialEntityExtractor` for Vietnamese phone/price/location/intent extraction.
- Redis Stream `stream:social:raw_posts` producer from Python adapter.
- Basic unit and integration tests for regex and Redis stream.

**Scope (Moved to Stories 21.8a–f):**
- MCP streamable-http transport (21.8a)
- Redis stream consumer Celery wiring (21.8b)
- Multi-domain target expansion (21.8c)
- Universal scrape target mapper (21.8d)
- Per-account proxy and cookie binding (21.8e)
- XActions governance and health integration (21.8f)

**Status:** `[done]` foundation; `[reopened]` for 21.8a–f
```

### 4.2 `epics.md` — Add Stories 21.8a–f

Sau Story 21.8, thêm mới:

```markdown
### Story 21.8a: MCP StreamableHTTP Transport for XActions

As a Nowing backend engineer,
I want `XActionsSocialAdapter` to connect to XActions via streamable HTTP MCP,
So that I can reuse sessions, avoid spawning subprocesses, and honor consumer quota.

**Acceptance Criteria:**
- **Given** `XACTIONS_MCP_URL`, `XACTIONS_MCP_API_KEY`, `XACTIONS_CONSUMER_ID` configured, **When** `XActionsMcpClient` connects, **Then** it uses `mcp.client.streamable_http.streamablehttp_client` and maintains a reusable session.
- **Given** a tool call, **When** XActions returns a 3-layer JSON envelope, **Then** the client parses `success`, `data`, `meta`, `summary`, and `datasetArtifactPath` correctly.
- **Given** `XACT_4291` or `PROXY_EXHAUSTED`, **When** error occurs, **Then** client raises `XActionsMcpError` with `retryAfter` for downstream handling.

_AD-SOC-1 · AD-SOC-4 · AD-SOC-11 · TRINITY-4_

### Story 21.8b: Redis Stream Consumer Celery Wiring

As a Nowing backend engineer,
I want `run_social_stream_consumer` to run as a Celery beat task,
So that ingested social posts are processed into `SocialPost` and `Lead` records continuously.

**Acceptance Criteria:**
- **Given** messages in `stream:social:raw_posts`, **When** `process_social_stream` Celery task runs, **Then** it reads via consumer group `social_processors`, persists posts, creates leads for high-intent posts, evaluates `AlertRule`, and ACKs messages.
- **Given** a failed message, **When** processing throws, **Then** it moves to `stream:social:failed` DLQ and ACKs the original.
- **Given** Celery beat, **When** every 30 seconds, **Then** `process_social_stream` is enqueued.

_AD-SOC-4 · AD-SOC-6 · AD-SOC-7_

### Story 21.8c: Multi-Domain Social Target Expansion

As a sales development representative,
I want to create monitored targets for multiple platforms (Facebook, Twitter, TikTok, Chợ Tốt, Shopee, TopCV, VietnamWorks, LinkedIn, Batdongsan, Mã số thuế, B2B registry),
So that I can ingest leads from any vertical source.

**Acceptance Criteria:**
- **Given** `POST /workspaces/{id}/social-monitored-targets`, **When** payload includes any supported platform, **Then** the target is validated and persisted.
- **Given** a target, **When** scheduler checks due targets, **Then** it supports `facebook_group`, `facebook_page`, `twitter_keyword`, `twitter_user`, `tiktok_hashtag`, `chotot_category`, `shopee_keyword`, `topcv_search`, `vietnamworks_search`, `linkedin_company`, `batdongsan_category`, `masothue_lookup`, `b2b_registry_search`.
- **Given** a target, **When** CRUD operations happen, **Then** GET/PATCH/DELETE endpoints work.

_AD-SOC-9 · AD-SOC-1_

### Story 21.8d: Universal Scrape Target Mapper

As a Nowing backend engineer,
I want a mapper that converts a `SocialMonitoredTarget` into the correct XActions tool and arguments,
So that the scheduler can dispatch any platform without per-platform `if/else` blocks.

**Acceptance Criteria:**
- **Given** a target with `platform` and `target_id`, **When** `UniversalScrapeTargetMapper.map(target)` runs, **Then** it returns `(tool_name, arguments)` for the matching XActions tool.
- **Given** Facebook group/page, **When** mapped, **Then** it returns `x_facebook_group_posts` or `x_facebook_posts`.
- **Given** Twitter keyword/user, **When** mapped, **Then** it returns `x_search_tweets` or `x_get_tweets`.
- **Given** any other supported platform, **When** mapped, **Then** it returns `x_scrape(platform, action, args)` or `x_crawl_post` fallback.

_AD-SOC-9 · AD-SOC-4_

### Story 21.8e: Per-Account Proxy and Cookie Binding

As a sales development representative,
I want each target to use its own XActions account and proxy,
So that scraping is resilient to blocks and follows platform policies.

**Acceptance Criteria:**
- **Given** a target with `account_id` and `proxy_url`, **When** scheduler runs, **Then** XActions is called with those values.
- **Given** no target-level account, **When** scheduler runs, **Then** it falls back to `XACTIONS_FACEBOOK_ACCOUNT_ID` or `x_facebook_list_accounts`.
- **Given** per-workspace account/proxy binding, **When** persisted, **Then** it is stored in `xactions_proxy_bindings`.

_AD-SOC-3 · AD-SOC-11_

### Story 21.8f: XActions Governance and Health Integration

As a Nowing platform admin,
I want to see XActions governor status, stream metrics, and alerts in Nowing admin dashboard,
So that I can detect scraping issues early.

**Acceptance Criteria:**
- **Given** admin telemetry, **When** `x_governor_status` is called, **Then** it displays healthy proxy count, consumer quota, and backpressure status.
- **Given** admin telemetry, **When** `x_admin_stream_metrics` is called, **Then** it displays stream length, consumer lag, and throughput.
- **Given** `x_admin_stream_alerts` breach, **When** it occurs, **Then** Nowing sends alert via Telegram/Email.

_AD-SOC-11 · AD-SOC-7_
```

### 4.3 `sprint-status.yaml`

**OLD:**
```yaml
  21-8-social-ingress-via-xactions-integration: done
```

**NEW:**
```yaml
  21-8-social-ingress-via-xactions-integration: done  # baseline: schema, extractor, producer tests
  21-8a-mcp-streamablehttp-transport: in-progress
  21-8b-redis-stream-consumer-celery-wiring: in-progress
  21-8c-multi-domain-social-target-expansion: backlog
  21-8d-universal-scrape-target-mapper: backlog
  21-8e-per-account-proxy-cookie-binding: backlog
  21-8f-xactions-governance-health-integration: backlog
```

### 4.4 Architecture Spine

**OLD (không có ghi chú về stdio):**

```markdown
* **AD-SOC-4 [ADOPTED]: Dual-Channel Microservice Communication**
  * *Kênh Đồng Bộ:* Nowing kết nối sang XActions Daemon qua **MCP over HTTP/SSE Transport** (Port 3001)...
```

**NEW (thêm note):**

```markdown
* **AD-SOC-4 [ADOPTED]: Dual-Channel Microservice Communication**
  * *Kênh Đồng Bộ:* Nowing kết nối sang XActions Daemon qua **MCP over HTTP/SSE Transport** (Port 3001) với Persistent Connection Pool. **Note (2026-09-09):** `XActionsSocialAdapter` hiện tại vẫn dùng stdio subprocess — cần chuyển sang `streamablehttp_client` theo Story 21.8a.
```

### 4.5 Code — `adapter.py` refactor

Xem `INTEGRATION-PLAN-2026-09-09.md` phần 4.2/4.3 để biết `XActionsMcpClient` thay thế `stdio_client`.

### 4.6 Code — `celery_app.py`

Thêm vào beat schedule:

```python
"process-social-stream": {
    "task": "process_social_stream",
    "schedule": crontab(second="*/30"),
    "options": {"expires": 25},
},
```

Thêm `app.tasks.celery_tasks.social_stream_worker` vào `include`.

### 4.7 Code — `app/config/entities.py`

Thêm:

```python
XACTIONS_MCP_URL: str = "http://xactions:3001/mcp"
XACTIONS_MCP_API_KEY: str | None = None
XACTIONS_CONSUMER_ID: str = "nowing"
XACTIONS_FACEBOOK_ACCOUNT_ID: str | None = None
```

---

## Section 5 — Implementation Handoff

### Scope Classification: **Moderate-to-Major**

- **Moderate:** Stories 21.8a, 21.8b, 21.8d (code refactor, Celery wiring, mapper) — Developer agent có thể làm trực tiếp.
- **Major:** Story 21.8c (multi-domain) cần coordination với XActions team (expose `x_scrape`); 21.8f cần Admin UI.

### Handoff Recipients

| Vai trò | Trách nhiệm |
|---|---|
| **Product Owner** | Phê duyệt scope mở rộng 21.8a–f; cập nhật sprint backlog; thông báo team về việc mở lại Story 21.8 |
| **System Architect (Winston)** | Giám sát AD-SOC-1..11; review `XActionsMcpClient` và `UniversalScrapeTargetMapper` |
| **Developer Agent** | Implement 21.8a, 21.8b, 21.8d; refactor `adapter.py`, `celery_app.py`, `social_routes.py`, `social_xactions_ingest.py` |
| **XActions Team** | Expose `x_scrape` tool; đảm bảo thin event stream từ mọi crawler; document action matrix |
| **Frontend Developer** | Cập nhật social target form với multi-platform dropdown |
| **QA/DevOps** | Chạy shadow-run parity; verify Redis stream consumer không tích tụ |

### Success Criteria

- `XActionsMcpClient` kết nối được `http://xactions:3001/mcp` với session reuse.
- `process_social_stream` chạy trong Celery beat, xử lý messages, tạo `SocialPost` + `Lead`.
- `SUPPORTED_PLATFORMS` mở rộng ít nhất 8 platform.
- Stream consumer lag không vượt quá 10.000 messages trong 5 phút.
- Admin dashboard hiển thị `x_governor_status`.

---

## Section 6 — Checklist Completion

- [x] **1.1** Trigger: Story 21.8 baseline done, integration plan reveals gaps.
- [x] **1.2** Problem: premature completion, missing transport/consumer/multi-domain.
- [x] **1.3** Evidence: code references for stdio, 2-platform, unwired consumer.
- [x] **2.1** Epic 21 still viable, needs scope expansion.
- [x] **2.2** Add sub-stories 21.8a–f; create/reopen Epic 21.8.
- [x] **2.3** Epic 26 and 29 indirectly impacted.
- [x] **3.1** PRD: Trinity alignment still valid; AC of Story 21.8 need rewrite.
- [x] **3.2** Architecture: AD-SOC-4 note about stdio gap.
- [x] **3.3** UI/UX: social target form needs multi-platform dropdown.
- [x] **3.4** Tests, config, migrations, Celery, Docker need updates.
- [x] **4.1** Direct Adjustment selected.
- [x] **4.4** Rationale: avoid rollback, preserve foundation, expand scope.
- [x] **5.1–5.5** Proposal sections complete.
- [x] **6.4** `sprint-status.yaml` update provided.

---

**Cần phê duyệt:** Bạn có đồng ý mở lại Story 21.8 và thêm 6 sub-stories 21.8a–f như đề xuất? Nếu đồng ý, tôi sẽ bắt đầu apply các thay đổi vào `epics.md`, `sprint-status.yaml`, `ARCHITECTURE-SPINE.md`, và code adapter/Celery.
