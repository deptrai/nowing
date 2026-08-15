# Story 16.5: National Public Procurement & Tender Intelligence (muasamcong.mpi.gov.vn)

Status: done

<!-- Governed by architecture-muasamcong-procurement-2026-08-15 (AD-PROC-1 to AD-PROC-8) -->

## Story

As a corporate bidding team or government contractor,
I want to ingest public procurement tenders (TBMT) and vector-search E-HSMT dossiers from `muasamcong.mpi.gov.vn`,
So that I can identify high-value bidding opportunities, track bid deadlines, and summarize qualification criteria using AI.

## Acceptance Criteria

1. **Given** search criteria (keyword, province/location, procurement field, price range), **When** `MuasamcongScraper` is executed, **Then** it queries the e-GP v2.0 REST API (`https://muasamcong.mpi.gov.vn/api/v1/tender/notice/search` and detail endpoints) with a Token-Bucket rate limiter enforcing a maximum of 15 requests/minute per IP/proxy (AD-PROC-1, AD-PROC-4).
2. **Given** tender records from e-GP v2.0, **When** persisted to PostgreSQL, **Then** records are saved into `procurement_tenders` with composite unique constraint `(bid_no, bid_turn_no)`, normalized `bid_price NUMERIC(18, 2)`, ISO 8601 timestamps, and status (`active`, `closed`, `cancelled`) (AD-PROC-6).
3. **Given** associated bidding dossiers (E-HSMT PDF/ZIP files up to 200MB), **When** downloaded and ingested, **Then** the worker streams binary data directly to S3/MinIO in 128KB chunks using `aioboto3` (peak RAM $\le 32$MB), extracts text with `pypdf`/`pdfplumber`, generates 1536-dim embeddings, and stores chunks into `procurement_tender_chunks` with HNSW index (`vector_cosine_ops`) (AD-PROC-2, AD-PROC-3).
4. **Given** a tender record, **When** analyzed by `ai_summarizer`, **Then** it extracts 4 core qualification criteria: (1) Doanh thu bình quân hàng năm (Turnover requirements), (2) Hợp đồng tương tự (Similar contract experience), (3) Nhân sự chủ chốt (Key personnel), (4) Bảo đảm dự thầu (Bid security/guarantee) and calculates countdown time remaining (marking `urgent` when $< 48$h) (AD-PROC-8).
5. **Given** an AI Agent session, **When** invoking capabilities `procurement_search_tenders(keyword, field, min_price, max_price, location)` or `procurement_summarize_hsmt(bid_no, bid_turn_no)`, **Then** matched procurement opportunities with qualification summaries, deadline countdown, and procuring entity details are returned (AD-PROC-7).

## Architectural Invariants Mapping

- **AD-PROC-1**: REST Microservice Ingress Path (`muasamcong.mpi.gov.vn/api/v1/tender/notice/*`)
- **AD-PROC-2**: Asynchronous Large Document Offloading (S3 128KB chunked streaming via `aioboto3`, peak RAM $\le 32$MB)
- **AD-PROC-3**: High-Performance HNSW Vector Indexing (`embedding vector(1536)` on tenders & chunks)
- **AD-PROC-4**: Vietnamese ISP Proxy Pool & Anti-WAF Token-Bucket Rate Limiting ($\le 15$ req/min)
- **AD-PROC-5**: Auto-Tender Matching & Alert Engine Dispatch
- **AD-PROC-6**: Idempotent Ingestion with Composite Bid ID `(bid_no, bid_turn_no)`
- **AD-PROC-7**: AI Agent Capability Tools (`procurement_search_tenders`, `procurement_summarize_hsmt`)
- **AD-PROC-8**: Live Countdown Timer & Deadline Status Tracking ($< 48$h urgency threshold)

## Review Findings & Fixes Applied (2026-08-15)

- [x] RF-1: SSRF Protection for `dossier_url` — Whitelisted `muasamcong.mpi.gov.vn`, `egp.mpi.gov.vn`, blocked internal cloud metadata/private IPs (`validate_dossier_url`).
- [x] RF-2: AWS S3 Multipart 5MB Part Buffering — Enforced `MIN_S3_PART_SIZE_BYTES = 5 * 1024 * 1024` buffer while maintaining 128KB HTTP stream (peak RAM $\le 32$MB).
- [x] RF-3: Timezone UTC+7 — Corrected `_parse_iso_datetime` to convert naive Vietnam local timestamps (+07:00) to UTC instead of naive assignment.
- [x] RF-4: HNSW Vector Indexes — Added `Index("idx_procurement_chunk_embedding_hnsw", "embedding", postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"})`.
- [x] RF-5: VND Dot Price Parsing — Handled dot-formatted currency (`45.000.000.000 VND`).
- [x] RF-6: Non-blocking CPU PDF Parsing — Added `extract_text_from_pdf_stream_async` via `asyncio.to_thread`.
- [x] RF-7: Infinite Loop Guard — Set `step_size = max(char_chunk_size - char_overlap, 1)`.
- [x] RF-8: ZIP Dossier Support — Added auto-detection and extraction for ZIP dossiers.
- [x] RF-9: Price & Bid Validation — Added `min_price <= max_price` validator and string bounds.
- [x] RF-10: Degradation Status — Added `degraded` and `degradation_reason` to `ProcurementSummarizeOutput`.

## Tasks / Subtasks

- [x] Task 1: Database Models & Schema Definition (AC: 2, 3)
  - [x] 1.1 Định nghĩa model `ProcurementTender` trong `nowing_backend/app/proprietary/platforms/muasamcong/models.py` với composite unique key `(bid_no, bid_turn_no)`.
  - [x] 1.2 Định nghĩa model `ProcurementTenderChunk` với `embedding Vector(1536)` và foreign key cascading.
- [x] Task 2: e-GP v2.0 REST API Client & Scraper (AC: 1, 2)
  - [x] 2.1 Xây dựng `MuasamcongScraper` tại `nowing_backend/app/proprietary/platforms/muasamcong/scraper.py`.
  - [x] 2.2 Tích hợp Token-Bucket Rate Limiter giới hạn $\le 15$ req/min, exponential backoff và proxy support.
  - [x] 2.3 Normalize dữ liệu tender: parse ngày tháng ISO 8601 UTC, tiền tệ VND, status lifecycle.
- [x] Task 3: Dossier Service & 128KB S3 Chunk Streaming (AC: 3)
  - [x] 3.1 Xây dựng `TenderDossierService` tại `nowing_backend/app/proprietary/platforms/muasamcong/dossier_service.py`.
  - [x] 3.2 Tải stream 128KB chunks trực tiếp lên S3/MinIO qua `aioboto3` (bảo đảm memory footprint $\le 32$MB).
  - [x] 3.3 Text extraction từ PDF dossier, chunking (512 tokens / overlap 50) và vector embedding.
- [x] Task 4: AI Summary & Countdown Intelligence (AC: 4)
  - [x] 4.1 Xây dựng `ProcurementAISummarizer` tại `nowing_backend/app/proprietary/platforms/muasamcong/ai_summarizer.py` bóc tách 4 tiêu chí năng lực (doanh thu, HĐ tương tự, nhân sự, bảo đảm dự thầu).
  - [x] 4.2 Tính toán thời gian đóng thầu, countdown và cờ cảnh báo gấp `< 48h`.
- [x] Task 5: AI Agent Capabilities & Tools (AC: 5)
  - [x] 5.1 Đăng ký Capability `procurement.search` và `procurement.summarize` trong `nowing_backend/app/capabilities/procurement/`.
  - [x] 5.2 Xây dựng executors và schemas cho `procurement_search_tenders` và `procurement_summarize_hsmt`.
- [x] Task 6: Unit Tests & Quality Verification (AC: 1-5)
  - [x] 6.1 Unit test `tests/unit/proprietary/platforms/muasamcong/test_scraper.py`.
  - [x] 6.2 Unit test `tests/unit/proprietary/platforms/muasamcong/test_dossier_service.py`.
  - [x] 6.3 Unit test `tests/unit/proprietary/platforms/muasamcong/test_ai_summarizer.py`.
  - [x] 6.4 Unit test `tests/unit/capabilities/test_procurement_capabilities.py`.


## Dev Notes

- **Memory Safety Rule:** Tuyệt đối không đọc toàn bộ file HSMT vào RAM (`await resp.read()` bị cấm). Phải dùng `async for chunk in resp.aiter_bytes(chunk_size=131072)`.
- **Concurrency & Rate Limit:** Enforce TokenBucket 15 req/min, hỗ trợ cả async local token bucket lẫn redis-backed bucket khi có connection.
- **Dependencies:** `aioboto3>=13.0.0`, `pypdf>=4.0.0`, `pgvector>=0.3.0`, `httpx>=0.27.0`.

### References
- [Architecture Spine: _bmad-output/planning-artifacts/architecture/architecture-muasamcong-procurement-2026-08-15/ARCHITECTURE-SPINE.md]


