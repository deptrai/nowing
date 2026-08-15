# Architecture Spine — LinkedIn Jobs & B2B Executive Intelligence Engine

**Ngày lập:** 2026-08-15  
**Trạng thái:** `final`  
**Quyết định Kiến trúc chi phối (Architectural Invariants):** AD-LI-1 đến AD-LI-6  
**Epic liên kết:** Epic 21B (B2B Lead Intelligence) & Epic 12 (Executive Recruitment)  
**Tác giả:** Winston (BMAD System Architect)  

---

## 1. Mục Tiêu & Phạm Vi Hệ Thống

Thu thập dữ liệu việc làm công khai và hồ sơ doanh nghiệp B2B từ LinkedIn:
* Cào hàng nghìn việc làm mới mỗi ngày không cần tài khoản qua **Public Guest Jobs API**.
* Xác định các doanh nghiệp đang mở rộng quy mô (Hiring Growth Signals) làm đầu vào cho B2B Lead Gen.
* Ánh xạ hồ sơ lãnh đạo cấp cao (Decision Makers) cho các chiến dịch B2B Sales Outreach.

---

## 2. Các Quyết Định Kiến Trúc Bắt Buộc (Architectural Invariants)

* **AD-LI-1 [ADOPTED]: Zero-Login Public Guest Jobs API Ingestion**
  * Khai thác endpoint `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search` và `/api/jobPosting/{id}` với `httpx` + `selectolax`. Hoàn toàn không dùng tài khoản đăng nhập để tránh rủi ro checkpoint/ban.
* **AD-LI-2 [ADOPTED]: Rotating Residential Proxy Pool & Human Jitter**
  * Sử dụng proxy xoay vòng; mỗi request cách nhau random 1.5–3.5s; Token Bucket $\le 25$ req/phút/IP.
* **AD-LI-3 [ADOPTED]: Company Headcount Growth Signal Detection**
  * Tự động tính toán số lượng tin tuyển dụng mới của từng doanh nghiệp trong 30 ngày qua (`active_jobs_count`) để chấm điểm tiềm năng B2B Intent Score.
* **AD-LI-4 [ADOPTED]: Executive Decision Maker Mapping via Public Dorking**
  * Trích xuất thông tin C-Level/VP/Director từ Google SERP / Company Public Pages mà không quét trực tiếp profile cá nhân sau login wall.
* **AD-LI-5 [ADOPTED]: Idempotent Job & Company Persistence**
  * Ràng buộc duy nhất `job_id VARCHAR(100)` cho tin tuyển dụng và `company_slug VARCHAR(255)` cho doanh nghiệp.
* **AD-LI-6 [ADOPTED]: AI Agent Tool Registration**
  * Đăng ký `linkedin_search_jobs` và `linkedin_lookup_company_executives` cho Nowing Agent.

---

## 3. Mô Hình Cơ Sở Dữ Liệu (PostgreSQL DDL)

```sql
CREATE TABLE IF NOT EXISTS linkedin_companies (
    id BIGSERIAL PRIMARY KEY,
    company_slug VARCHAR(255) NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    website TEXT,
    industry VARCHAR(255),
    headcount_range VARCHAR(50), -- '11-50', '51-200', '1000+'
    headquarters VARCHAR(255),
    active_jobs_count INT DEFAULT 0,
    decision_makers JSONB DEFAULT '[]'::jsonb, -- [{ "name": "...", "title": "CEO", "linkedin_url": "..." }]
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS linkedin_jobs (
    id BIGSERIAL PRIMARY KEY,
    job_id VARCHAR(100) NOT NULL UNIQUE,
    company_id BIGINT REFERENCES linkedin_companies(id) ON DELETE SET NULL,
    company_name VARCHAR(255) NOT NULL,
    title TEXT NOT NULL,
    location VARCHAR(255),
    workplace_type VARCHAR(50), -- 'On-site', 'Hybrid', 'Remote'
    seniority_level VARCHAR(50), -- 'Entry level', 'Mid-Senior', 'Director'
    employment_type VARCHAR(50), -- 'Full-time', 'Contract'
    description_text TEXT,
    skills TEXT[],
    posted_at TIMESTAMPTZ,
    raw_entities JSONB DEFAULT '{}'::jsonb,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_li_jobs_company_name ON linkedin_jobs(company_name);
CREATE INDEX IF NOT EXISTS idx_li_jobs_posted ON linkedin_jobs(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_li_jobs_gin_entities ON linkedin_jobs USING gin (raw_entities);
CREATE INDEX IF NOT EXISTS idx_li_jobs_embedding_hnsw ON linkedin_jobs USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_li_companies_slug ON linkedin_companies(company_slug);
```
