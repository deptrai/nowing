# Sprint Change Proposal — Nowing: Remove Duplicate Canonical Index / Vertical Search (2026-08-08)

**Workflow:** `bmad-correct-course`  
**Project:** Nowing  
**Date:** 2026-08-08  
**Author:** Winston (System Architect)  
**Status:** ✅ **ADOPTED (decisions 1–3)** — PO/Owner approved 2026-08-08; Q4 default = do not keep `canonical_entities` as product-state table in Nowing.

**Loại thay đổi:** Architecture alignment / cross-project boundary cleanup

**Đối ứng với:**
- `chainlens-research/_bmad-output/planning-artifacts/architecture/architecture-chainlens-research-2026-08-08/ARCHITECTURE-SPINE.md` (final, 2026-08-08)
- `chainlens-research/_bmad-output/planning-artifacts/ecosystem-vision-chainlens-nowing-2026-08-08.md`
- `chainlens-research/_bmad-output/planning-artifacts/epics.md` (Epic 47 mới)

**Artifacts bị ảnh hưởng:**
- `_bmad-output/planning-artifacts/epics.md`
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- (thứ cấp) `README.md`, `docs/`, MCP tool catalog

---

## 1. Issue Summary

Kiến trúc ecosystem mới đã chốt:

> `chainlens-research` = Exa-like universal search engine, own single canonical index for public web + shared vertical data.  
> `Nowing` = end-user product + domain scrapers + private data + data acquisition.  
> `Nowing` scrapers feed `chainlens-research`; `Nowing` chat queries `chainlens-research` first.

Tuy nhiên, `nowing/_bmad-output/planning-artifacts/epics.md` hiện vẫn chứa nhiều epic/story xây **canonical index + vertical search riêng** trong Nowing, dẫn tới:

1. **Duplicate storage + duplicate indexing** của cùng một vertical data (BĐS, jobs, news, finance, company).
2. **Canonical index bị phân mảnh** — một nửa ở `chainlens-research`, một nửa ở `Nowing`.
3. **Mất khả năng re-use** — mỗi domain lại xây dedupe/merge/search_text/embed một lần.
4. **Vi phạm AD-1, AD-3, AD-6** của architecture spine 2026-08-08.

**Quyết định đề xuất:**
- `chainlens-research` là chỗ **duy nhất** có `pgvector` canonical index + hybrid search cho public/vertical data.
- `Nowing` vẫn build **domain scrapers** (BĐS, jobs, news, finance, company) nhưng output phải là `Chunk[]` gửi về `chainlens-research` qua `POST /v1/ingest/scraper`.
- `Nowing` vẫn giữ `Memory` (private user memory, chat context, extracted facts) nhưng **không dùng `Memory` làm search corpus cho web/vertical content**.

---

## 2. Scope of Change

### 2.1 REMOVE / consolidate into `chainlens-research`

| Epic | Story | Lý do remove/re-scope |
|---|---|---|
| **Epic 13** | 13.1 Canonical Persistence, Tenancy & Convention | Tạo `canonical_entities` + `canonical_entity_sources` + `canonical_merge_history` + `canonical_persist_outbox` với `embedding`, `search_text`, `to_tsvector`, HNSW/GIN — đây là **Nowing building its own canonical index**. |
| **Epic 13** | 13.2a–e BDS/Jobs persistence, merge history, PII canonicalization, dedup benchmark | Lưu và index BDS/jobs entities trong Nowing. |
| **Epic 13** | 13.3 Unified Search API | RRF search across documents + canonical entities trong Nowing. |
| **Epic 10** | 10.4 Vietnam BĐS Listing Aggregator & Cross-Source Trust Score | AC ghi "mở rộng `Memory`/`ResearchThread` để lưu aggregated listing" + "query via REST/MCP với filter" = Nowing search corpus. |
| **Epic 12** | 12.4 Vietnam Job Aggregator | AC ghi `vn_jobs.aggregate` trả kết quả với filter location/price/source qua REST/MCP/chat = Nowing search corpus. |
| **Epic 14** | 14.1 RSS Feed Integration | AC "articles appear in unified search results" = Nowing index news. |
| **Epic 14** | 14.2 News Entity Extraction | AC "all mentioning articles are returned" dựa trên canonical entity index trong Nowing. |
| **Epic 15** | 15.1 CafeF Financial Data | AC "market news appear in workspace search" = Nowing index finance. |
| **Epic 16** | 16.1 masothue.com Company Data | Nếu AC bao gồm searchable company corpus = cần re-scope. |
| **Epic 12** | 12.7 Property Price Alerts | Depends on Epic 13 canonical entities. |
| **Epic 12** | 12.8 Cross-Source Entity Timeline | Depends on Epic 13 canonical storage. |

### 2.2 KEEP — nhưng bổ sung AC feed `chainlens-research`

| Epic | Story | Thay đổi |
|---|---|---|
| Epic 10 | 10.1–10.3 BĐS scrapers | Giữ. Thêm AC: normalize thành `Chunk[]`, gọi `POST /v1/ingest/scraper` với `source: 'nowing_scraper'`. |
| Epic 12 | 12.1–12.3 VietnamWorks/TopCV/ITviec scrapers | Giữ. Thêm AC tương tự. |
| Epic 2 | 2.6–2.8 Indeed/Walmart/Amazon scrapers | Giữ. Thêm AC tương tự. |
| Epic 12 | 12.5 PII Redaction | Giữ. Chạy **trước khi gửi** chunks qua `chainlens-research`. |
| Epic 12 | 12.9 Saved Searches | Giữ, nhưng saved search query target là `chainlens-research`, không phải Nowing index. |
| Epic 12 | 12.6 Job Market Alerts | Giữ, nhưng alert trigger = re-run scraper + feed index, không tự search local. |

### 2.3 KEEP — vì là product state / private memory

| Epic | Story | Lý do giữ |
|---|---|---|
| Epic 3 | 3.1–3.16 KB + Long-Term Memory | `Memory` là workspace memory (user docs, chat facts, auto-extract). Đây là **private user data**, không phải public/vertical search corpus. Kiến trúc mới vẫn cho phép `Nowing` giữ product state + private data. |
| Epic 9 | 9.x ChainLens Integration | Giữ, cần mở rộng cho gap-fill + private provider. |
| Epic 18 | 18.x Vertical Client Platform | Giữ public chat API / Agent Registry. Search bên dưới phải đi qua `chainlens-research`. |

### 2.4 ARCHITECTURE-SPINE Nowing cần bỏ

- **AD-27** — Nowing canonical entity convention (fingerprint/merge/search_text) → chuyển sang `chainlens-research`.
- **AD-28** — Unified matching-engine trigger trong Nowing → chuyển sang `chainlens-research`.
- Các tham chiếu `canonical_entities` / `pgvector` index trong `Epic 13` scope → xóa.

---

## 3. New Data Flow

```
[Nowing scraper: BĐS/jobs/news/finance/company]
         │
         ▼ normalize to Chunk[]
[POST /v1/ingest/scraper @ chainlens-research]
         │
         ▼ embed + index
[chainlens-research canonical index]
         │
         ▼ query
[Nowing chat/agent calls POST /api/v1/search]
         │
         ▼ answer with citations + costDollars
[Nowing user]
```

Private data flow vẫn giữ:

```
[Nowing user query private scope]
         │
         ▼ chainlens-research classifies private-scope
[POST /v1/private-data/search @ Nowing]
         │
         ▼ Nowing fetches connector docs, applies RLS
[NowingPrivateProvider returns Chunk[]]
         │
         ▼ chainlens-research merges + answers
```

---

## 4. Artifact Changes

### 4.1 `nowing/_bmad-output/planning-artifacts/epics.md`

| Hành động | Chi tiết |
|---|---|
| Mark Epic 13 `[REMOVED]` | Ghi rõ lý do: superseded by `chainlens-research` canonical index. Các story 13.1–13.3 không làm. |
| Re-scope 10.4 | Bỏ AC "query/filter" và "lưu vào Memory/ResearchThread". Thêm AC feed `chainlens-research`. |
| Re-scope 12.4 | Bỏ AC "filter by location/price/source" qua REST/MCP/chat. Thêm AC gửi `Chunk[]` tới `chainlens-research`. |
| Re-scope 14.1, 14.2, 15.1, 16.1 | Bỏ AC "workspace search". Thêm AC `Chunk[]` feed. |
| Re-scope 12.7, 12.8 | Không phụ thuộc Epic 13. Timeline/alerts build trên `chainlens-research` index hoặc product state nhỏ. |
| Update 10.1–10.3, 12.1–12.3, 2.6–2.8 AC | Thêm `POST /v1/ingest/scraper` step. |
| Cập nhật Epic List | Bỏ Epic 13 khỏi active list hoặc đánh dấu REMOVED. |

### 4.2 `nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`

| Hành động | Chi tiết |
|---|---|
| Xóa AD-27, AD-28 | Hoặc đánh dấu `[REMOVED — moved to chainlens-research]`. |
| Bổ sung AD mới: `AD-34` Nowing scrapers feed `chainlens-research` | Rule: domain scraper output must be `Chunk[]` with `source: 'nowing_scraper'` and pushed to `POST /v1/ingest/scraper`. |
| Bổ sung AD mới: `AD-35` Nowing does not build public/vertical search corpus | Rule: `Memory`/`ResearchThread` keep private user facts and conversation state; web/vertical search queries route through `chainlens-research`. |
| Cập nhật AD-11 | Làm rõ `Memory` embedding chỉ dùng cho **private workspace memory**, không phải vertical search corpus. |

### 4.3 `nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`

| Hành động | Chi tiết |
|---|---|
| Thêm Non-Goal | NG-X: Nowing does not build a canonical web/vertical index; canonical search lives in `chainlens-research`. |
| Sửa FR-43..FR-47 / FR-48 | Đổi wording từ "index/aggregate/search in Nowing" sang "scrape + normalize + feed to `chainlens-research`". |
| Cập nhật FR-24/FR-37/FR-38 | Bổ sung gap-fill + private provider contract. |

---

## 5. Migration Path

### Đã done (không revert)

- Epic 10.1–10.3, 12.1–12.3 scraper code đã chạy — không revert.
- Epic 10.4, 12.4 aggregator code đã có — không xóa code ngay, chỉ **ngừng mở rộng search/index** và chuyển hướng feed.

### Cần làm ngay sau approve

1. **Tạo `NowingIngestService`** gọi `POST /v1/ingest/scraper`.
2. **Sửa aggregator output** từ `Memory`/`ResearchThread` sang `Chunk[]` + `ingestJobId`.
3. **Gỡ search/filter endpoints** của aggregator (nếu đã expose).
4. **Xóa/dừng Epic 13** — chưa implement thì bỏ.
5. **Cập nhật MCP tool catalog** — `nowing_chotot_bds_scrape` vẫn tồn tại nhưng kết quả đi vào `chainlens-research`.

### Không cần làm

- Không xóa `Memory` table hay `Memory.search` — private user memory vẫn OK.
- Không thay đổi chat flow cơ bản — `chainlens.research` vẫn là công cụ.

---

## 6. Risks & Mitigations

| Rủi ro | Mức độ | Giảm thiểu |
|---|---|---|
| `chainlens-research` `POST /v1/ingest/scraper` chưa tồn tại | High | Epic 47 (story 47-1) cần ship trước hoặc song song. Dùng temporary queue nếu cần. |
| `Memory`/`ResearchThread` đang lưu aggregated listing | Medium | Tắt dần write path; không xóa dữ liệu cũ ngay. |
| User đã quen query BĐS/jobs qua Nowing MCP | Medium | MCP tool vẫn tồn tại, kết quả đi qua `chainlens-research` search thay vì local query. |
| Private data leak vào `chainlens-research` | High | `NowingPrivateProvider` không pre-index; gọi on-demand. Audit AC. |
| Cross-project auth/cost chưa rõ | Medium | Story 47-4 xử lý service auth; 47-2 xử lý cost allocation. |

---

## 7. Decision Needed

**Approver:** PO/Owner (Luisphan)

**Câu hỏi cần trả lời:**
1. Đồng ý remove Epic 13 hoàn toàn? (Y/N)
2. Đồng ý re-scope 10.4 + 12.4 sang feed `chainlens-research`? (Y/N)
3. Đồng ý bỏ AD-27/AD-28 trong Nowing spine? (Y/N)
4. Có muốn giữ lại một phần `canonical_entities` trong Nowing như **product state table** (không search) cho timeline/alerts? (Y/N — nếu Y cần scope rõ)

**Nếu approve 1–3:** Tôi sẽ edit `epics.md`, `ARCHITECTURE-SPINE.md`, và cập nhật sprint-status.yaml.
