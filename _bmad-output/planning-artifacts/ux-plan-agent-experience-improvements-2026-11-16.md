# Kế hoạch cải thiện Agent Experience — Nowing (v2)

**Ngày:** 2026-11-16 (v2 — đã re-rank qua party-mode review)
**Nguồn:** Case study lead-gen trầm hương (`/tmp/leadgen-tramhuong/CASE_STUDY_v2.md`) + audit session hermes daingan-ops (`20261116_172811_ff6a2174`)
**Soạn bởi:** Mary + Sally + party-room consensus (Winston/Amelia/Murat/John/Victor)
**Trạng thái:** Draft v2 — chờ review trước khi tách epic/story

---

## 1. Bối cảnh

Hai case study thực tế cho thấy cùng một vấn đề gốc:

- **Pi session (trầm hương):** 14 bugs fix tại chỗ để flow chạy được; agent bên trong Nowing không có cách persist leads → phải thêm tool `save_leads`; 362 leads thu được nhưng chỉ sau khi sửa nhiều lớp lỗi.
- **Hermes daingan-ops:** agent ngoài chọn bypass hoàn toàn chat harness — import `LeadBatchService` trực tiếp qua `sys.path.insert` + `os.chdir` (fragile), vì không có API surface chính thức. Mất 46 browser calls để tìm trang leads.

**Kết luận chung:** Nowing hoạt động, nhưng "đường đi đúng" cho cả agent trong-lẫn-ngoài đều không tồn tại hoặc không khám phá được. User (người và agent) vấp vào: thất bại vô hình, ngõ cụt không lối thoát, và thiếu cửa sau chính thức.

## 2. Personas

| Persona | Mô tả | Journey chính |
|---|---|---|
| **P1 — External agent** | Bot tự trị (hermes, cron worker) đẩy leads vào Nowing | Discover API → authenticate → push leads → verify → handle errors |
| **P2 — Internal agent** | Chat agent trong Nowing (subagent tool calls) | Nhận yêu cầu → chọn nguồn → scrape → persist → báo cáo |
| **P3 — Human operator** | User điều khiển/giám sát qua UI | Gõ yêu cầu → theo dõi turn → approve/HITL → xem leads |

## 3. Quyết định từ party review (v2)

Ba tranh luận đã giải quyết:

1. **A-vs-B ordering → song song theo lane, không xếp hàng.** B1 rẻ → chạy trước; A1 là nền → chạy song song và *là điều kiện* cho B3 (`scrapers/health` cần chính status semantics của A1).
2. **Scope A1 → boundary-only.** Không chuẩn hóa 3 schema executor/gateway/proxy — bọc một adapter `ToolResultEnvelope` ở ranh giới tool→agent. Hint map seed từ đúng 4 code đã gặp trong case study (MEDIRUS_4001/4010/4030/5000), forward `suggestedAction` từ Medirus, không viết từ điển cho lỗi chưa xảy ra.
3. **E1 thăng hạng → Lane cấp cứu.** +800MB RSS/turn là blocker âm thầm cho multi-user; **profile trước (py-spy/tracemalloc trên `stream_new_chat`), fix sau** — cấm đoán fix.
4. **Điều kiện của Sally:** B1 ship kèm tối thiểu **A3** (doc-persist guard) — agent đẩy data vào mà mất âm thầm thì cửa sau vỡ niềm tin.
5. **Murat:** mọi phase phải có **risk column**; test bằng **fake MCP fixture**, không e2e server thật.

## 4. Plan v2 — theo lane

### Lane 1 — Cửa sau (P1) — chạy ngay

| # | Hạng mục | Effort | Risk |
|---|---|---|---|
| B1 | Tài liệu hóa + mở `POST /api/v1/workspaces/{id}/leads/batch-ingest` cho PAT scoped `leads:write`; ví dụ curl + Python | **Vừa** *(nâng — cần thiết kế PAT bypass `require_session_context` an toàn)* | PAT leak → ingest sai workspace; authz design sai → mở cửa quá rộng |
| A3 | Documents write không mất âm thầm khi embedding fail → lưu doc, flag `unindexed` *(ship cùng B1)* | Nhỏ | Doc unindexed không searchable — phải surface flag cho user |

### Lane 2 — Cấp cứu (P2/P3) — điều tra song song

| # | Hạng mục | Effort | Risk |
|---|---|---|---|
| E1 | Memory spike +800MB/turn: **py-spy/tracemalloc trên `stream_new_chat` finalize** → fix sau khi có data | Nhỏ (điều tra) | Đoán fix sai chỗ; profiler overhead khi đo |

### Lane 3 — Nền status contract (P1+P2+P3)

| # | Hạng mục | Effort | Risk |
|---|---|---|---|
| A1 | `ToolResultEnvelope` ở boundary (gateway/proxy/executor→agent): `{status: ok\|empty\|failed\|degraded, reason, recovery_hint, items}`; forward `suggestedAction`; hint map cho 4001/4010/4030/5000 | Vừa | Đổi shape tool result → agent prompt parse sai; normalization che mất lỗi gốc |
| A2 | Recovery hint chi tiết cho từng kênh chết: credential cần + file cần sửa + lệnh retest | Nhỏ | Hint cũ khi Medirus thay đổi error |
| B2 | `nowing_mcp` tools: `leads.ingest`, `leads.list`, `tables.create`, `credits.balance` | Vừa | MCP tool surface mới cần auth scope riêng |
| B3 | `GET /api/v1/scrapers/health` — per-channel status/last error/credential cần *(dùng contract A1)*; reuse cho UI dashboard | Vừa | Health check probe làm kênh chết thêm chết (rate limit) |

### Lane 4 — Resilience & journey (P2+P3)

| # | Hạng mục | Effort | Risk |
|---|---|---|---|
| C1 | Fix HITL-approve → `functionResponse count mismatch` (Gemini) — cần fixture checkpoint-state để test | Vừa | Test khó seed (history dài ~52 messages); fix sai → chết turn khác |
| C2 | Regenerate trên thread crash: offer "gửi tin nhắn mới" thay 400 | Nhỏ | — |
| C3 | Step-cap graceful degrade: luôn synthesize partial + liệt kê tool results | Vừa | Partial answer có thể khiến user tưởng hoàn tất |
| C4 | Progress narrative cho long turns | Vừa | Nhiễu stream format |
| D1 | Route thật `/dashboard/{id}/leads` (không alias) | Nhỏ | Redirect cũ phải tương thích |
| D2 | `save_leads` auto-chọn/tạo table mặc định — cấm `table_id=NULL` | Nhỏ | Auto-table phình nếu agent tạo tràn lan |
| D3 | Empty state leads table hướng dẫn dùng chat | Nhỏ | — |

### Lane 5 — Quét dọn

| # | Hạng mục | Effort | Risk |
|---|---|---|---|
| E2 | Gateway forward `context.workspaceId` → Medirus (stream events đang bị drop) | Nhỏ | — |
| E3 | `NOWING_DEV_BYPASS_QUOTA` hoặc admin topup UI — khỏi SQL surgery | Nhỏ | Bypass lọt vào prod → mất kiểm soát |

## 5. Test & fixture yêu cầu (Murat)

- **Fake MCP server fixture** trả deterministic `MEDIRUS_4xxx` — bắt buộc cho A1/A2/B3 tests; không e2e server thật.
- **Checkpoint-state fixture** (history ~52 messages, duplicate functionResponse) cho C1.
- **Load-test billing advisory lock** — key sai → serialize toàn bộ debit workspace.
- **Baseline RSS benchmark** trước/sau `stream_new_chat` cho E1.

## 6. Tiêu chí nghiệm thu (tổng)

- **B1+A3:** Agent ngoài push 10 leads qua PAT+REST, không import internal code; leads hiện trong canvas table; embed fail vẫn có document row với flag.
- **A1+A2+B3:** Gọi scrape vào kênh chết → envelope `status=failed` + `reason` + `recovery_hint` (credential cụ thể); `scrapers/health` trả đúng trạng thái; fake-MCP fixture pass.
- **C:** Approve HITL trên Gemini → turn hoàn tất; step-cap → partial answer (không `text=0`); regenerate → offer thay 400.
- **D:** `/dashboard/1/leads` mở đúng canvas; `save_leads` không table_id → vẫn hiện trong auto-table.
- **E:** RSS/turn <200MB sau fix; không còn `MissingWorkspaceId`; dev topup không cần SQL.

## 7. Ngoài phạm vi (ghi nhận, chưa làm)

- Provision credentials thật: FB cookie pool, `YOUTUBE_API_KEY`, Zalo/IG accounts, residential proxy cho Shopee, Telegram relay :3800 — cần owner cung cấp.
- Refactor `dainganxanh` `mcp.sh` → `mcp_client.py` (đã ghi vào SOUL.md của daingan-ops, bot tự làm khi chạm vào).
- `_prepare_lead_record` drop `contact_name` → fix riêng (workaround: truncate 55).

## 8. Changelog

- **v1** (2026-11-16): Proposal gộp Mary+Sally, rank theo UX journey.
- **v2** (2026-11-16): Party-room re-rank — B1+E1 lên lane đầu (song song), A1 rescope boundary-only, thêm risk column + fixture requirements, Sally's A3 gắn cùng B1.
- **v3** (2026-11-16): Append §9-10 — định hướng platform 2 chiều + thiết kế `CampaignSpec` mở rộng (party-room).
- **v4** (2026-11-16): Append §11 — Invariants (Winston architecture review): AD-1..6 + deferred invariants.

---

## 9. Định hướng thương mại hóa — Platform 2 chiều (party-room v3)

Quyết định của owner: Nowing lead-gen định vị là **intelligence platform hai chiều**, không phải lead-data service.

- **Hai phía:** seller post campaign brief ("tìm người mua cho X") ↔ buyer/business post nhu cầu ("tôi cần nguồn hàng sỉ Y"). Nowing ở giữa là matching engine biến social noise thành intent.
- **Network effect nằm trong corpus**, không giữa hai phía: mỗi campaign chạy xong làm giàu channel-map, intent regex, dedup graph — seller sau hưởng lợi seller trước.
- **Monetize seller side** (mỗi lead = doanh số); **buyer side là inventory** — intake free, đa số intent vẫn đến từ mining (comments) chứ không cần chiêu mộ buyer post.
- **Pricing:** pay-per-match có SLA, không pay-per-lead — contact sai/dedup trùng → auto-refund (cơ chế `auto_refund` + advisory lock đã có trong billing).
- **Sequence bắt buộc (John):** (1) **Concierge** — team săn tay qua chat, bán pack để chứng minh người trả tiền; (2) **Productized** — campaign spec self-serve + automations recurring; (3) **Platform** — buyer-side intake + match queue + shared corpus. Bỏ qua chặng 1 = chết cold start.
- **Điều kiện pháp lý (Murat):** B2C personal data không pool xuyên workspace (PDPD); B2B business-public entities được pool. Lead-quality SLA định lượng ngay từ đầu.
- **Rủi ro mở:** trầm hương chỉ là n=1 — cần vertical thứ hai chứng minh generalize; buyer-side consent khi mine comment cá nhân.

## 10. Thiết kế `CampaignSpec` hai chiều (party-room v3)

Hiện trạng (`app/lead_intelligence/campaign/schemas.py`): spec đã có `icp_criteria`, `intent_tags`, `signal_triggers`, `source_budgets`, `excluded_identities`, `schedule` — nhưng hardcode một chiều (chủ campaign tìm entities khớp ICP).

### Diff đề xuất (migration sạch — toàn field mới có default)

```python
class CampaignSpec(BaseModel):
    ...  # giữ nguyên mọi field hiện tại
    direction: Literal["demand", "supply"] = "demand"         # demand=tôi bán tìm người mua; supply=tôi cần tìm nhà cung cấp
    match_mode: Literal["mine", "pool", "hybrid"] = "mine"   # pool/hybrid gated sau platform_b2b corpus
    supply_criteria: SupplyCriteria | None = None              # chỉ khi direction=supply
    corpus_scope: Literal["workspace", "platform_b2b"] = "workspace"
    visibility: Literal["private", "poolable"] = "private"   # leads có vào shared pool không

class SupplyCriteria(BaseModel):
    categories: list[str]
    locations: list[str]
    require_tax_id: bool = True
    min_rating: float = 0.0
    require_verified: bool = False

# campaign_leads.role = "buyer" | "supplier" | "partner"
# (role là thuộc tính của (campaign, lead) — junction, KHÔNG phải entity attr:
#  spa là 'buyer' trong campaign trầm hương, 'seller' trong campaign của chủ spa)
```

### Nguyên tắc đã chốt

- **Cùng một engine/spec cho cả hai chiều** — buyer intake là `CampaignSpec(direction="supply")`, không phải form riêng (UI intake chỉ map vào subset: cần gì / ở đâu / mức giá).
- **`match_mode="pool"` là chặng-3** — gated sau `platform_b2b` corpus + consent; ngày đầu pool chỉ trong workspace.
- **Corpus phân tầng:** B2B entities shareable (`platform_b2b`), B2C personal siloed (`workspace`). `excluded_identities` mở rộng thành corpus-level dedup graph khi pool mở.
- **Abuse guard:** `visibility` + rate-limit per tenant — chặn supply campaign bị dùng để build DB đối thủ/lộ supply chain.
- **Routing:** `resolve_adapters_for_campaign` nhận thêm `direction` → supply-side route Maps/masothue/registry, demand-side route comment-mining channels.
- **Effort ước tính (Amelia):** spec + routing ≈ 1 tuần; shared corpus + pool matching là phase riêng.

## 11. Invariants (Winston review — bắt buộc trước epic split)

Các AD sau ràng buộc mọi item trong plan — hai implementer độc lập không được chọn lệch.

- **AD-1 — Lead-write funnel ở service layer.** *Binds:* mọi ghi vào `leads` (REST ingest, `save_leads`, `multi_source_lead_gen`, scripts, MCP tools). *Rule:* auto-table (tạo/chọn default table khi `table_id` thiếu) sống trong `LeadBatchService.ingest_batch` hoặc layer nó gọi — KHÔNG ở tool layer. *Prevents:* B1 REST ingest tái tạo orphan `table_id=NULL` mà D2 chỉ fix ở chat path.
- **AD-2 — PAT authz contract.** *Binds:* B1 + mọi endpoint mở cho external agent sau này. *Rule:* scope model khai báo trước (đầu tiên `leads:write`), revocation/rotation, audit attribution per-token (ai push lead nào — PDPD bắt buộc). Bypass `require_session_context` phải qua một seam có tên, không phải flag rải rác. *Prevents:* hai implementer hai mô hình scope khác nhau.
- **AD-3 — Một `ToolResultEnvelope` xuyên mọi boundary.** *Binds:* gateway tools, REST endpoints mới, `nowing_mcp` tools. *Rule:* `{status, reason, recovery_hint, items}` là schema duy nhất trả cho agents — không được có kiểu `failed` thứ hai. *Prevents:* ba contract status khác nhau (đúng loại bug plan đang đi fix).
- **AD-4 — Ingest contract.** *Binds:* B1 + `leads.ingest` MCP. *Rule:* pin trước idempotency key (dedupe theo gì), validation (`_reject_degenerate_leads` ≥1 contact field), semantics `client_id`, conflict behavior khi HMAC trùng. *Prevents:* hai external agent push cùng shape, nhận hai outcome.
- **AD-5 — `CampaignSpec` joint validation.** *Binds:* §10. *Rule:* ma trận hợp lệ cho `direction × match_mode × corpus_scope × visibility` — tổ hợp vô nghĩa (vd `pool` + `workspace`) bị reject tại schema validation, không phải runtime. *Prevents:* cấu hình hợp lệ về type nhưng không tồn tại được về semantics.
- **AD-6 — Repro trước fix cho correctness bugs.** *Binds:* C1 (HITL mismatch), E1 (memory spike), mọi "remaining bug". *Rule:* fixture tái hiện + root cause chứng minh trước khi viết fix — kỷ luật áp cho E1 áp cho cả C1. *Prevents:* fix đoán mò bằng spec của bug.

### Deferred invariants (ghi tên, không quyết định bây giờ)

- **Single lock rule:** mọi workspace-scoped debit path bắt buộc qua `pg_advisory_xact_lock` cùng key scheme — pin khi có writer thứ hai ngoài `charge_capability`.
- **Single credit authority:** user-level vs workspace-level balance (`auto_pin_invalid` root cause) — E3 chỉ là bypass; quyết khi touch quota system lần tới.
- **Config contract:** single source cho port/URL service (:4445/:3200/:3333) — chống tái phát login-loop env-drift.
- **B3 = cached aggregation**, không live probe — pin trong story B3 (health endpoint không được trở thành load lên kênh chết).
