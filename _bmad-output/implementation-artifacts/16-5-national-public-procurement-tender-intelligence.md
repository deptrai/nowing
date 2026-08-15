# Story 16.5: National Public Procurement & Tender Intelligence (muasamcong.mpi.gov.vn)

Status: ready-for-dev

<!-- Note: Governed by architecture-muasamcong-procurement-2026-08-15 (AD-PROC-1 to AD-PROC-8) -->

## Story

As a corporate bidding team or government contractor,
I want to ingest public procurement tenders (TBMT) and vector-search E-HSMT dossiers from `muasamcong.mpi.gov.vn`,
So that I can identify high-value bidding opportunities, track bid deadlines, and summarize qualification criteria using AI.

## Acceptance Criteria

1. **Given** search criteria (e.g. province, procurement field, price range), **When** `MuasamcongScraper` is executed, **Then** it queries the e-GP v2.0 REST API at `muasamcong.mpi.gov.vn/api/` with a token-bucket rate limiter enforcing a maximum of 15 requests/minute.
2. **Given** tender records, **When** persisted to PostgreSQL, **Then** records are saved into `procurement_tenders` with composite unique constraint `(bid_no, bid_turn_no)` and status (`pending`, `active`, `closed`).
3. **Given** associated bidding dossiers (E-HSMT PDF/ZIP files up to 200MB), **When** downloaded, **Then** the worker streams binary data directly to S3/MinIO in 128KB chunks using `aioboto3` (peak RAM $\le 32$MB), extracts text with `pypdf`/`pdfplumber`, and stores chunk embeddings (`vector(1536)`) into `procurement_tender_chunks` with an HNSW index (`vector_cosine_ops`).
4. **Given** a user viewing tender intelligence in Nowing Web, **When** the tender detail card is rendered, **Then** a live countdown timer displays the exact time remaining until bid closing (turning red when $< 48$h remaining) alongside an AI-generated Executive Summary of qualification criteria.
5. **Given** an AI Agent session, **When** invoking `procurement_search_tenders(field, min_price, max_price)` or `procurement_summarize_hsmt(bid_no)`, **Then** matched procurement opportunities with extracted qualification requirements and contact info are returned.

## Tasks / Subtasks

- [ ] Task 1: Database Schema & Vector Storage Migration (AC: 2, 3)
  - [ ] 1.1 Tạo bảng `procurement_tenders` (`id`, `bid_no`, `bid_turn_no`, `project_name`, `procuring_entity`, `investor`, `field`, `bid_price`, `bid_closing_at`, `dossier_url`, `status`, `created_at`, `CONSTRAINT uq_procurement_tender UNIQUE (bid_no, bid_turn_no)`).
  - [ ] 1.2 Tạo bảng `procurement_tender_chunks` (`id`, `tender_id`, `chunk_index`, `content`, `section_title`, `embedding vector(1536)`, `created_at`).
  - [ ] 1.3 Tạo Alembic migration với chỉ mục HNSW `idx_procurement_chunks_embedding` và B-tree `idx_procurement_bid_closing`.
- [ ] Task 2: e-GP v2.0 REST API Client & Rate Limiter (AC: 1, 2)
  - [ ] 2.1 Xây dựng `MuasamcongScraper` tại `nowing_backend/app/proprietary/platforms/muasamcong/scraper.py`.
  - [ ] 2.2 Tích hợp Redis Token Bucket Rate Limiter giới hạn $\le 15$ req/min.
  - [ ] 2.3 Phân tích JSON response, chuẩn hóa giá gói thầu `NUMERIC(18, 2)` và thời gian đóng thầu ISO 8601.
- [ ] Task 3: S3 128KB Streaming & PDF Vectorization (AC: 3)
  - [ ] 3.1 Xây dựng `TenderDossierService` tại `nowing_backend/app/proprietary/platforms/muasamcong/dossier_service.py`.
  - [ ] 3.2 Tải stream 128KB chunks trực tiếp lên S3 qua `aioboto3` (giữ RAM worker $\le 32$MB).
  - [ ] 3.3 Trích xuất text PDF, phân đoạn (chunking 512 tokens) và sinh embedding lưu vào database.
- [ ] Task 4: AI Summary & Countdown UX Contract (AC: 4)
  - [ ] 4.1 Xây dựng AI Summarizer trích xuất 4 mục cốt lõi: Yêu cầu doanh thu, Kinh nghiệm hợp đồng tương tự, Nhân sự chủ chốt, Tiền bảo đảm dự thầu.
  - [ ] 4.2 Cung cấp API trả về dữ liệu Countdown Timer cho frontend Widget U2.
- [ ] Task 5: AI Agent Capability & Tools (AC: 5)
  - [ ] 5.1 Đăng ký Capability `procurement.tenders` trong `app/capabilities/procurement/`.
  - [ ] 5.2 Định nghĩa Agent Tools `procurement_search_tenders` và `procurement_summarize_hsmt`.
- [ ] Task 6: Unit & Integration Tests (AC: 1-5)
  - [ ] 6.1 `tests/unit/platforms/test_muasamcong_parser.py` (Parser test với fixture JSON e-GP v2.0).
  - [ ] 6.2 `tests/unit/platforms/test_s3_chunk_streaming.py` (Mock streaming upload $\le 32$MB memory footprint).
  - [ ] 6.3 `tests/integration/platforms/test_procurement_vector_search.py` (Vector cosine similarity search).

## Dev Notes

- **Architecture Invariants:** Tuân thủ AD-PROC-1 đến AD-PROC-8 trong `architecture-muasamcong-procurement-2026-08-15/ARCHITECTURE-SPINE.md`.
- **Memory Safety Rule:** Tuyệt đối không đọc toàn bộ file HSMT 200MB vào bộ nhớ RAM (`content = await resp.read()` bị cấm). Phải dùng `async for chunk in resp.aiter_bytes(chunk_size=131072)`.
- **Dependencies:** `aioboto3>=13.0.0`, `pypdf>=4.0.0`, `pgvector>=0.3.0`.

### References
- [Architecture Spine: architecture-muasamcong-procurement-2026-08-15/ARCHITECTURE-SPINE.md]
- [UX Contract: ux-contract-scrapers-expansion-and-lead-intelligence.md#U2]
