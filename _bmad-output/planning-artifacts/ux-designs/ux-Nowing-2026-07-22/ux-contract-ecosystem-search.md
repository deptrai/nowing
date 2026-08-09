# UX Contract — Ecosystem Search (chainlens-research results)

**Ngày:** 2026-08-08  
**Phạm vi:** UX cho chat/agent khi kết quả tìm kiếm đến từ `chainlens-research` canonical index thay vì local Nowing knowledge base.  
**Bám vào:** FR-58, FR-59, FR-62, AD-34, AD-35. 
> **Note:** `AD-27` (canonical entity convention) and `AD-28` (unified domain engine) are owned by `chainlens-research`; this contract cites `AD-34` and `AD-35` for the Nowing-side feed and search boundary instead. 
**Loại tài liệu:** *contract* — định nghĩa trạng thái UI phải biểu diễn được, không định layout/màu.

---

## 1. Bài toán UX

`chainlens-research` là chỗ duy nhất own canonical index cho public/vertical data. Nowing chat/agent nhận kết quả từ `POST /api/v1/search` và cần hiển thị sao cho:
- User tin tưởng nguồn dữ liệu.
- User phân biệt được kết quả từ public web (`chainlens-research`) vs private workspace (`NowingPrivateProvider`).
- User thấy provenance (nguồn gốc, domain, thời gian crawl).
- Citation click đưa user về đúng source hoặc chunk window.

Hệ quả UX:
- Không còn "canonical entity card merged from N sources" trong Nowing UI — `chainlens-research` trả về đã merged/reranked.
- Citation model thay đổi: từ local `Chunk.id` sang `chainlens-research` `sourceId` + `domain`.
- Cần trạng thái đợi index (ingest job in progress) khi scraper mới gửi dữ liệu.

---

## 2. Contract — các trạng thái UI bắt buộc

### 2A. Search Result Citation (Agent response)

| # | Trạng thái | Bắt buộc |
|---|---|---|
| A1 | **Source badge** — Mỗi citation hiển thị domain/source label (e.g. `vnexpress.vn`, `vietnamworks.com`) | ✅ |
| A2 | **Public vs Private indicator** — Citation có icon/label phân biệt `public` (chainlens-research) vs `private` (workspace memory/connector) | ✅ |
| A3 | **Fetched-at timestamp** — Citation hiển thị thời điểm dữ liệu được crawl/index | ✅ |
| A4 | **Confidence / source count** — Khi `chainlens-research` trả `confidence_score` + `source_count`, hiển thị subtle indicator | 🟡 optional |
| A5 | **Citation link behavior** — Click citation mở source URL (nếu public) hoặc document chunk window (nếu private) | ✅ |
| A6 | **Provenance drawer** — Long-press / "View sources" mở drawer liệt kê các source gốc (nếu `chainlens-research` trả nhiều source cho cùng entity) | 🟡 optional |

### 2B. Ingest / Sync Status (after scraper run)

| # | Trạng thái | Bắt buộc |
|---|---|---|
| B1 | **Ingest pending** — Sau khi scraper/aggregator gửi `Chunk[]`, hiển thị "Indexing..." cho đến khi `ingestJobId` hoàn thành | ✅ |
| B2 | **Ingest success** — Khi `chainlens-research` báo done, hiển thị "N items indexed" | ✅ |
| B3 | **Ingest failed** — Khi `ingestJobId` failed, hiển thị lỗi + retry action (chỉ retry gửi, không retry scrape trừ khi yêu cầu) | ✅ |
| B4 | **Gap-fill in progress** — Khi agent trigger `POST /v1/gap-fill`, hiển thị "Researching..." với estimated time / progress | ✅ |

### 2C. Empty / Degraded States

| # | Trạng thái | Bắt buộc |
|---|---|---|
| C1 | **No public data** — Khi `chainlens-research` trả empty, hiển thị "No indexed public data found. Trigger deep research?" + action | ✅ |
| C2 | **Engine unavailable** — Khi `chainlens-research` timeout/5xx, degrade sang private workspace search + banner "Deep research temporarily unavailable" | ✅ |
| C3 | **Partial results** — Khi `chainlens-research` trả partial, hiển thị banner kèm nguồn nào bị thiếu | ✅ |

---

## 3. Ràng buộc kỹ thuật UX

- **Citation component** — Tái dùng `CitationBadge` với prop `variant` = `public` | `private`.
- **Source URL resolution** — Public citation cần `source_url` từ `chainlens-research`; private citation dùng local `Document`/`Chunk` route.
- **Async state** — Ingest job state được theo dõi qua SSE hoặc polling; chat không block chờ index.
- **i18n** — Labels "public" / "private" / "indexing" localize.
- **Accessibility** — Citation list keyboard navigable, timestamp có `title` đầy đủ.

---

## 4. User Flows

### Flow 1: User asks for market overview
1. User: "căn hộ Thủ Đức giá bao nhiêu"
2. Agent gọi `chainlens-research` `POST /api/v1/search`.
3. Results trả về merged BĐS data từ `batdongsan.com.vn`, `chotot.com`, `muaban.net`.
4. Agent response có citations: `[1] batdongsan.vn · 2h ago`, `[2] chotot.com · 5h ago`.
5. Click `[1]` mở source URL; long-press mở provenance drawer.

### Flow 2: Scraper feeds chainlens-research
1. User chạy `vn_jobs.aggregate`.
2. Nowing gửi `Chunk[]` tới `chainlens-research`.
3. UI hiển thị "Indexing 47 jobs...".
4. Khi `ingestJobId` done, UI chuyển "47 jobs indexed".
5. User chat "tìm việc Python senior" → agent trả kết quả từ canonical index.

---

## 5. Truy vết

- Chặn: Epic 47 (chainlens-research), FR-58, FR-59.
- Phụ thuộc: AD-34 (`Chunk` contract), AD-35 (no local search corpus).
- Reuses: `ux-contract-async-deep-research` (async state), `ux-contract-usage-dashboard` (cost/attribution).

---

## 6. Open Questions

1. **Confidence indicator** — Có hiển thị số confidence trực tiếp hay chỉ màu dot?
2. **Provenance drawer depth** — Liệt kê tất cả source URLs hay chỉ domain list?
3. **Gap-fill progress** — Hiển thị estimated time hay chỉ spinner?
