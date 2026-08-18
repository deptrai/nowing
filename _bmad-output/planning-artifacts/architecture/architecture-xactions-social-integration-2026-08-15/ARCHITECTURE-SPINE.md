# Architecture Spine — XActions Universal Scraping Microservice Integration (Social, E-Commerce, Real Estate & HR)

**Ngày lập:** 2026-08-15  
**Cập nhật mới:** 2026-08-18 (Nâng cấp toàn diện thành Universal Scraping Engine)  
**Trạng thái:** `final`  
**Quyết định Kiến trúc chi phối (Architectural Invariants):** AD-SOC-1 đến AD-SOC-10  
**Epic liên kết:** Epic 21A (Social Lead Generation & Universal Scraping Ingestion)  
**Tác giả:** Winston (BMAD System Architect)  
**Tích hợp:** Sử dụng trực tiếp `XActions` Universal Scraping Microservice (`/Users/luisphan/Documents/GitHub/XActions`)  

---

## 1. Mục Tiêu & Phạm Vi Hệ Thống

Ủy quyền toàn bộ tác vụ cào dữ liệu đa nền tảng cho **XActions Universal Scraping Microservice** để:
* Thu thập dữ liệu **Mạng xã hội** (Facebook, X/Twitter, Threads, TikTok, Instagram).
* Thu thập dữ liệu **Thương mại điện tử** (Shopee VN, TikTok Shop).
* Thu thập dữ liệu **Bất động sản** (Chợ Tốt bóc tách SĐT chính chủ, Batdongsan.com.vn).
* Thu thập dữ liệu **Tuyển dụng & B2B Leads** (TopCV, VietnamWorks, LinkedIn qua CDP Port 9222).
* Tự động bóc tách **Intent Signals** (Ý định Mua/Bán BĐS, Tuyển dụng, Đầu tư) và Số điện thoại đưa vào Nowing Lead CRM & Alert Engine.
* Tinh giản Nowing backend: Loại bỏ 100% các scraper cũ và browser dependencies khỏi Nowing Docker image.

---

## 2. Các Quyết Định Kiến Trúc Bắt Buộc (Architectural Invariants)

* **AD-SOC-1 [ADOPTED]: Zero-Reinvention Universal Scraping Delegation**
  * Không lập trình lại module cào dữ liệu trong Nowing. Nowing đóng vai trò là AI Orchestrator & Knowledge Hub, giao tiếp với `XActions` qua Model Context Protocol (MCP) và Redis Event Streams.
* **AD-SOC-2 [ADOPTED]: Stealth Anti-Detection & Fingerprint Delegation**
  * Ủy quyền toàn bộ cơ chế TLS/JA4 spoofing, Playwright Signer Bridge (`a_bogus`, `msToken`, `transaction-id`), và cookie warmup cho XActions.
* **AD-SOC-3 [ADOPTED]: Sticky SOCKS5 & Resilient Proxy Pool**
  * Tận dụng hệ thống ProxyIpPool tập trung của XActions với cơ chế auto-quarantine 5 phút và chống rò rỉ WebRTC/DNS.
* **AD-SOC-4 [ADOPTED]: Decoupled Redis Stream Event Buffer (`stream:social:raw_posts`)**
  * Dữ liệu cào từ XActions được đẩy vào Redis Stream dạng Thin Event Pointers (`MAXLEN ~ 20000`), tách rời khỏi tiến trình NLP bóc tách Entity và tính toán Embedding Vector của Nowing.
* **AD-SOC-5 [ADOPTED]: Automated Intent Classification & Entity Normalization**
  * Tự động gán nhãn `intent_tag` (`sell`, `buy`, `hiring`, `seeking`) và bóc tách SĐT/Email/Giá tiền vào `raw_entities JSONB`.
* **AD-SOC-6 [ADOPTED]: Idempotent Social & Lead Post Storage**
  * Ràng buộc duy nhất `(platform, external_post_id)`. Cập nhật số lượt reaction, bình luận, shares theo thời gian thực mà không trùng bản ghi.
* **AD-SOC-7 [ADOPTED]: Realtime Alert & CRM Lead Creation**
  * Bài đăng mang intent mua/bán ngay lập tức kích hoạt `AlertEngine` và tạo bản ghi Lead trong Nowing Lead Hub (Epic 21).
* **AD-SOC-8 [ADOPTED - NEW]: 3-Tier Incremental Gap-Filling Ingestion Protocol**
  * Quy trình truy xuất 3 tầng:
    1. *L1 Cache (Nowing DB):* Kiểm tra dữ liệu đã qua tinh chế AI (<15p).
    2. *L2 Cache (XActions DB):* Nếu thiếu/stale, hỏi XActions kho dữ liệu thô.
    3. *L3 Live Scraping:* XActions chỉ cào trên Internet cho phần khoảng trống thời gian (Delta Gap qua `since_id` / timestamp), không cào lại bài cũ.
* **AD-SOC-9 [ADOPTED - NEW]: Universal Multi-Domain Scraping & Legacy Decommissioning**
  * Mở rộng adapter Nowing kết nối toàn bộ các domain (Ecom, BĐS, Tuyển dụng) sang XActions. Xóa bỏ 20+ thư mục scraper cũ trong `nowing_backend/app/proprietary/platforms/` và giảm kích thước Dockerfile của Nowing từ 4GB xuống <500MB.
* **AD-SOC-10 [ADOPTED - NEW]: Data Partitioning & Storage Retention Policy**
  * XActions lưu trữ Raw Data tạm thời với vòng đời 30 ngày (Hot Data TTL). Nowing lưu trữ vĩnh viễn các Leads, Verified Contacts và Vector Embeddings có giá trị thương mại.

---

## 3. Mô Hình Cơ Sở Dữ Liệu Nowing (PostgreSQL DDL)

```sql
CREATE TABLE IF NOT EXISTS social_monitored_targets (
    id BIGSERIAL PRIMARY KEY,
    platform VARCHAR(50) NOT NULL, -- 'facebook_group', 'facebook_page', 'twitter_keyword', 'tiktok_hashtag', 'chotot_category', 'shopee_keyword', 'topcv_search'
    target_id VARCHAR(255) NOT NULL, -- Group ID, Page ID, Search Query, Category Slug
    target_name TEXT NOT NULL,
    target_url TEXT,
    category VARCHAR(50) NOT NULL, -- 'bds', 'recruitment', 'crypto', 'tech', 'ecom', 'general'
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    realtime_stream BOOLEAN NOT NULL DEFAULT FALSE,
    scrape_interval_minutes INT DEFAULT 15,
    last_scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_social_target UNIQUE (platform, target_id)
);

CREATE TABLE IF NOT EXISTS social_posts (
    id BIGSERIAL PRIMARY KEY,
    target_id BIGINT REFERENCES social_monitored_targets(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL, -- 'facebook', 'twitter', 'tiktok', 'threads', 'shopee', 'chotot', 'topcv', 'linkedin'
    external_post_id VARCHAR(255) NOT NULL,
    category VARCHAR(50) DEFAULT 'general',
    author_name TEXT,
    author_id VARCHAR(255),
    author_url TEXT,
    post_url TEXT,
    content TEXT,
    intent_tag VARCHAR(50), -- 'sell', 'buy', 'hiring', 'seeking', 'news', 'other'
    reactions_count INT DEFAULT 0,
    comments_count INT DEFAULT 0,
    shares_count INT DEFAULT 0,
    raw_entities JSONB DEFAULT '{}'::jsonb, -- Chứa phone, email, price, location, salary
    media_urls TEXT[],
    embedding vector(1536),
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_social_post UNIQUE (platform, external_post_id)
);

CREATE INDEX IF NOT EXISTS idx_social_posts_platform_ext ON social_posts(platform, external_post_id);
CREATE INDEX IF NOT EXISTS idx_social_posts_published ON social_posts(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_social_posts_intent ON social_posts(intent_tag);
CREATE INDEX IF NOT EXISTS idx_social_posts_gin_entities ON social_posts USING gin (raw_entities);
CREATE INDEX IF NOT EXISTS idx_social_posts_embedding_hnsw ON social_posts USING hnsw (embedding vector_cosine_ops);
```
