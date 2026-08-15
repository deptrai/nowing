# Architecture Spine — National Public Procurement Intelligence Engine (`muasamcong.mpi.gov.vn`)

**Ngày lập:** 2026-08-15  
**Trạng thái:** `final`  
**Quyết định Kiến trúc chi phối (Architectural Invariants):** AD-PROC-1 đến AD-PROC-7  
**Epic liên kết:** Epic 23 (National Procurement & Tender Intelligence)  
**Tác giả:** Winston (BMAD System Architect)  

---

## 1. Mục Tiêu & Phạm Vi Hệ Thống

Thu thập, phân tích và giám sát toàn bộ thông tin đấu thầu công lập từ Hệ thống Mạng Đấu thầu Quốc gia e-GP v2.0 (`muasamcong.mpi.gov.vn`):
* Cào tự động Thông Báo Mời Thầu (TBMT), Kết Quả Lựa Chọn Nhà Thầu (KQLCNT), Kế Hoạch Lựa Chọn Nhà Thầu (KHLCNT).
* Bóc tách và vector hóa toàn văn Hồ Sơ Mời Thầu (HSMT dạng PDF/Word/Excel) bằng OCR & Knowledge Ingest pipeline.
* Bắn thông báo tức thời đến doanh nghiệp khi xuất hiện gói thầu phù hợp với hồ sơ năng lực (Tender Matchmaking Alert).

---

## 2. Các Quyết Định Kiến Trúc Bắt Buộc (Architectural Invariants)

* **AD-PROC-1 [ADOPTED]: REST Microservice Ingress Path**
  * Tương tác trực tiếp với API backend e-GP (`https://muasamcong.mpi.gov.vn/api/v1/tender/notice/search` và `/api/v1/tender/notice/detail/{bidNo}`).
* **AD-PROC-2 [ADOPTED]: Asynchronous Large Document Offloading (Celery + S3)**
  * File đính kèm HSMT (PDF/ZIP dung lượng 10MB–200MB) được tải ngầm vào S3 bucket `s3://nowing-procurement-docs/{bid_code}/`. Celery worker phân tích văn bản và tạo chunks đưa vào `pgvector` mà không chiếm dụng main memory.
* **AD-PROC-3 [ADOPTED]: High-Performance HNSW Vector Indexing**
  * Lưu trữ `embedding vector(1536)` trên bảng `procurement_tenders` và bảng `procurement_tender_chunks` với index `hnsw (embedding vector_cosine_ops)`.
* **AD-PROC-4 [ADOPTED]: Vietnamese ISP Proxy Pool & Anti-WAF Rate Limiting**
  * Sử dụng proxy IP Việt Nam (VNPT/Viettel/FPT) với Token-Bucket giới hạn $\le 15$ req/phút/IP để tránh bị WAF chặn hoặc kích hoạt CAPTCHA.
* **AD-PROC-5 [ADOPTED]: Auto-Tender Matching & Alert Engine Dispatch**
  * Đánh giá tự động gói thầu mới dựa trên tiêu chí: Lĩnh vực, Địa bàn, Giá trị gói thầu, và Điều kiện tiên quyết. Nếu khớp `AlertRule` $\rightarrow$ Bắn thông báo Telegram/Email cho người dùng.
* **AD-PROC-6 [ADOPTED]: Idempotent Ingestion with Composite Bid ID**
  * Khóa chính duy nhất `bid_code VARCHAR(100)` (Số TBMT). UPSERT bảo đảm không trùng lặp khi gói thầu được gia hạn thời điểm đóng thầu hoặc đính chính HSMT.
* **AD-PROC-7 [ADOPTED]: AI Agent Capability Tools**
  * Đăng ký công cụ `procurement_search_tenders(keyword, field, min_price, max_price)` và `procurement_summarize_hsmt(bid_code)`.

---

## 3. Mô Hình Cơ Sở Dữ Liệu (PostgreSQL DDL)

```sql
CREATE TABLE IF NOT EXISTS procurement_tenders (
    id BIGSERIAL PRIMARY KEY,
    bid_code VARCHAR(100) NOT NULL, -- Số TBMT (e.g. IB2400123456)
    bid_turn_no VARCHAR(10) NOT NULL DEFAULT '00', -- Số lần chỉnh sửa / lần đăng tải (00, 01, 02)
    bid_name TEXT NOT NULL,
    investor_name TEXT, -- Tên chủ đầu tư
    procuring_entity TEXT, -- Bên mời thầu
    bid_price NUMERIC(18, 2), -- Giá gói thầu VNĐ
    procurement_field VARCHAR(100), -- 'Xây lắp', 'Mua sắm hàng hóa', 'Dịch vụ tư vấn'
    bid_type VARCHAR(50), -- 'Rộng rãi trong nước', 'Chào hàng cạnh tranh'
    funding_source TEXT, -- Nguồn vốn
    bid_open_date TIMESTAMPTZ,
    bid_close_date TIMESTAMPTZ,
    location VARCHAR(255),
    document_urls TEXT[],
    raw_specs JSONB DEFAULT '{}'::jsonb,
    summary_md TEXT,
    embedding vector(1536),
    status VARCHAR(50) DEFAULT 'open', -- 'open', 'closed', 'cancelled'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_procurement_bid_turn UNIQUE (bid_code, bid_turn_no)
);

CREATE TABLE IF NOT EXISTS procurement_tender_chunks (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES procurement_tenders(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proc_tenders_code ON procurement_tenders(bid_code);
CREATE INDEX IF NOT EXISTS idx_proc_tenders_close_date ON procurement_tenders(bid_close_date);
CREATE INDEX IF NOT EXISTS idx_proc_tenders_field ON procurement_tenders(procurement_field);
CREATE INDEX IF NOT EXISTS idx_proc_tenders_embedding_hnsw ON procurement_tenders USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_proc_chunks_embedding_hnsw ON procurement_tender_chunks USING hnsw (embedding vector_cosine_ops);
```
