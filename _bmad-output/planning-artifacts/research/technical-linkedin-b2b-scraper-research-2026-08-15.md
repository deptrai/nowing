# Technical Research — LinkedIn Jobs & B2B People Directory Scraper

**Ngày nghiên cứu:** 2026-08-15  
**Tác giả:** BMAD Technical Research Team  
**Mục tiêu:** Khảo sát chi tiết phương thức khai thác dữ liệu việc làm công khai qua Guest Jobs API, trích xuất cấu trúc doanh nghiệp và danh bạ nhân sự cấp cao (Decision Makers) từ LinkedIn năm 2026 cho Epic 12 (HR/Recruitment) và Epic 21B (B2B Leads).

---

## 1. Tổng quan Kiến trúc LinkedIn Data Access

LinkedIn chia dữ liệu thành 2 tầng rõ rệt:
1. **Public Guest Tier (Zero-Auth / High Throughput):** Toàn bộ tin tuyển dụng (`/jobs`) được LinkedIn mở công khai cho GoogleBot và khách truy cập vãng lai (không đăng nhập). Đây là nguồn dữ liệu hợp pháp, không tốn account và có throughput cao.
2. **Authenticated Member Tier (Login Required / Strict Anti-Bot):** Profile cá nhân chi tiết, kết nối mạng lưới (1st/2nd/3rd degree connections). Cần bảo vệ nghiêm ngặt chống khóa tài khoản (`Voyager API` rate limit).

---

## 2. Phân tích Endpoints & Giao thức Thu thập

### 2.1. Public Guest Jobs API (`seeMoreJobPostings`)

* **Endpoint:** `GET https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search`
* **Query Parameters:**
  * `keywords`: Từ khóa chức danh (VD: `Software Engineer`, `Real Estate Director`).
  * `location`: Địa điểm (VD: `Vietnam`, `Ho Chi Minh City`, `Hanoi`).
  * `geoId`: Mã định danh địa lý của LinkedIn (VD: `104195383` cho Việt Nam).
  * `start`: Phân trang (0, 25, 50, 75...).
  * `f_TPR`: Lọc thời gian (`r86400` cho 24h qua, `r604800` cho 7 ngày qua).
* **Đặc điểm Response:**
  * Trả về HTML fragment chứa danh sách 25 thẻ `<li>` có cấu trúc rõ ràng.
  * Phân tích qua `selectolax` cực nhanh: `job-card-list__title`, `job-card-container__company-name`, `job-card-container__metadata-item`.

### 2.2. Chi tiết Tin tuyển dụng (Job Description API)

* **Endpoint:** `GET https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}`
* **Response:** HTML chi tiết gồm toàn bộ mô tả công việc (JD), yêu cầu kinh nghiệm, mức lương (nếu có), quy mô công ty, và danh sách kỹ năng liên quan.

### 2.3. Company Insights & Executive Decision Makers

* **Cơ chế thu thập:**
  * Khai thác trang Company Life/About công khai: `https://www.linkedin.com/company/{company_slug}/about/`
  * Thu thập dữ liệu: Ngành nghề, quy mô nhân sự (`11-50`, `501-1000`), địa chỉ trụ sở, website chính thức.
  * Với danh bạ Decision Makers (C-Level, VP, Director): Kết hợp tra cứu Public Google SERP Dorking (`site:linkedin.com/in/ "CEO" "Company Name"`) để không vi phạm rate-limit tài khoản cá nhân.

---

## 3. Thách thức Kỹ thuật & Biện pháp Phòng vệ

| Thách thức | Chi tiết | Giải pháp Kỹ thuật |
| :--- | :--- | :--- |
| **IP-based Rate Limiting (HTTP 429)** | LinkedIn chặn IP sau ~100 requests guest liên tục. | Sử dụng Rotating ISP / Residential Proxies qua `httpx.AsyncClient` kết hợp random delay (1–3s). |
| **TLS & Header Fingerprinting** | Yêu cầu TLS Fingerprint giống trình duyệt thật (JA3 / HTTP/2 headers). | Bổ sung `curl_cffi` hoặc `httpx` với header browser chuẩn (`sec-ch-ua`, `sec-fetch-dest`, `accept-language`). |
| **Auth Wall khi xem Full Profile** | Khi xem quá 5 profile người dùng, LinkedIn buộc đăng nhập. | Áp dụng kỹ thuật Google Cache / SERP Snippet extraction thay vì truy cập trực tiếp URL `/in/` nếu không có session. |

---

## 4. Mô hình Dữ liệu Lưu trữ (PostgreSQL DDL)

```sql
CREATE TABLE IF NOT EXISTS linkedin_jobs (
    id BIGSERIAL PRIMARY KEY,
    job_id VARCHAR(100) NOT NULL UNIQUE,
    company_name VARCHAR(255) NOT NULL,
    company_url TEXT,
    title TEXT NOT NULL,
    location VARCHAR(255),
    workplace_type VARCHAR(50), -- 'On-site', 'Hybrid', 'Remote'
    seniority_level VARCHAR(50), -- 'Entry level', 'Mid-Senior level', 'Director'
    employment_type VARCHAR(50), -- 'Full-time', 'Contract', 'Part-time'
    description_text TEXT,
    skills TEXT[],
    posted_at TIMESTAMPTZ,
    raw_entities JSONB DEFAULT '{}'::jsonb,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS linkedin_companies (
    id BIGSERIAL PRIMARY KEY,
    company_slug VARCHAR(255) NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    website TEXT,
    industry VARCHAR(255),
    headcount_range VARCHAR(50),
    headquarters VARCHAR(255),
    decision_makers JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_linkedin_jobs_company ON linkedin_jobs(company_name);
CREATE INDEX IF NOT EXISTS idx_linkedin_jobs_posted ON linkedin_jobs(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_linkedin_jobs_gin_entities ON linkedin_jobs USING gin (raw_entities);
CREATE INDEX IF NOT EXISTS idx_linkedin_jobs_embedding_hnsw ON linkedin_jobs USING hnsw (embedding vector_cosine_ops);
```

---

## 5. Tích hợp Hệ sinh thái Nowing

1. **Epic 12 (Vietnam & Regional Job Market):** Hoàn thiện vertical tuyển dụng, tổng hợp tin việc làm cấp cao từ LinkedIn bên cạnh TopCV, VietnamWorks, ITviec.
2. **Epic 21 (B2B Lead Intelligence):** Phát hiện tín hiệu công ty mở rộng (Job Intent Signals) để tự động gợi ý danh sách Decision Makers phục vụ email outreach.
3. **Agent Capability (`linkedin_search_jobs`, `linkedin_lookup_company`):** Cung cấp công cụ tra cứu hồ sơ doanh nghiệp trực tiếp trong Nowing Chat.
