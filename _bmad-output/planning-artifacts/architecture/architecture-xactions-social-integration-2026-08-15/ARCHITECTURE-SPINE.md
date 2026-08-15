# Architecture Spine — XActions Social Intelligence Integration (Facebook & X/Twitter)

**Ngày lập:** 2026-08-15  
**Trạng thái:** `final`  
**Quyết định Kiến trúc chi phối (Architectural Invariants):** AD-SOC-1 đến AD-SOC-7  
**Epic liên kết:** Epic 21A (Social Lead Generation & Social Graph Ingestion)  
**Tác giả:** Winston (BMAD System Architect)  
**Tích hợp:** Sử dụng trực tiếp `XActions` MCP Engine (`/Users/luisphan/Documents/GitHub/XActions`)  

---

## 1. Mục Tiêu & Phạm Vi Hệ Thống

Tích hợp nền tảng tự động hóa và khai thác dữ liệu mạng xã hội chuyên sâu `XActions` vào Nowing để:
* Thu thập bài đăng, bình luận, thành viên nhóm từ **Facebook Groups & Fanpages** (`x_facebook_group_posts`, `x_facebook_group_comments`, `x_facebook_search`, `x_facebook_marketplace`).
* Thu thập tweet, keyword stream, trends, sentiment từ **X / Twitter** (`x_get_tweets`, `x_search_tweets`, `x_monitor_keyword`, `x_get_analytics`).
* Tự động bóc tách **Intent Signals** (Ý định Mua/Bán BĐS, Tuyển dụng, Đầu tư) và Số điện thoại khách hàng đưa vào Lead CRM & Alert Engine.

---

## 2. Các Quyết Định Kiến Trúc Bắt Buộc (Architectural Invariants)

* **AD-SOC-1 [ADOPTED]: Zero-Reinvention XActions Engine Integration**
  * Không lập trình lại module cào Facebook/Twitter từ đầu. Nowing đóng vai trò là Orchestrator và Storage Layer, giao tiếp với `XActions` qua MCP Tool Interface hoặc Internal Service Client.
* **AD-SOC-2 [ADOPTED]: Stealth Anti-Detection & Fingerprint Delegation**
  * Ủy quyền toàn bộ cơ chế Canvas/Audio/WebGL stealth fingerprinting, human-like mouse movement, scroll simulation và cookie warmup cho module `XActions/src/scrapers/facebook/fingerprint.js` và `human.js`.
* **AD-SOC-3 [ADOPTED]: Sticky SOCKS5 Residential Proxy Binding**
  * Mỗi tài khoản Facebook/Twitter trong `scraper_platform_accounts` được gán cố định 1-to-1 với một IP Proxy dân cư cố định nhằm tránh kích hoạt checkpoint 956/282 của Meta.
* **AD-SOC-4 [ADOPTED]: Decoupled Redis Stream Event Buffer (`stream:social:raw_posts`)**
  * Dữ liệu cào từ XActions được đẩy vào Redis Stream, tách rời khỏi tiến trình NLP bóc tách Entity và tính toán Embedding Vector.
* **AD-SOC-5 [ADOPTED]: Automated Intent Classification & Entity Normalization**
  * Tự động gán nhãn `intent_tag` (`sell`, `buy`, `hiring`, `seeking`) và bóc tách SĐT/Email/Giá tiền vào `raw_entities JSONB`.
* **AD-SOC-6 [ADOPTED]: Idempotent Social Post Storage**
  * Ràng buộc duy nhất `(platform, external_post_id)`. Cập nhật số lượt reaction, bình luận, shares theo thời gian thực mà không trùng bản ghi.
* **AD-SOC-7 [ADOPTED]: Realtime Alert & CRM Lead Creation**
  * Bài đăng mang intent mua/bán ngay lập tức kích hoạt `AlertEngine` và tạo bản ghi Lead trong Nowing Lead Hub (Epic 21).

---

## 3. Mô Hình Cơ Sở Dữ Liệu (PostgreSQL DDL)

```sql
CREATE TABLE IF NOT EXISTS social_monitored_targets (
    id BIGSERIAL PRIMARY KEY,
    platform VARCHAR(50) NOT NULL, -- 'facebook_group', 'facebook_page', 'twitter_keyword', 'twitter_user'
    target_id VARCHAR(255) NOT NULL, -- Group ID, Page ID, or Search Query
    target_name TEXT NOT NULL,
    target_url TEXT,
    category VARCHAR(50) NOT NULL, -- 'bds', 'recruitment', 'crypto', 'tech', 'general'
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
    platform VARCHAR(50) NOT NULL, -- 'facebook', 'twitter'
    external_post_id VARCHAR(255) NOT NULL,
    author_name TEXT,
    author_id VARCHAR(255),
    author_url TEXT,
    post_url TEXT,
    content TEXT,
    intent_tag VARCHAR(50), -- 'sell', 'buy', 'hiring', 'seeking', 'news', 'other'
    reactions_count INT DEFAULT 0,
    comments_count INT DEFAULT 0,
    shares_count INT DEFAULT 0,
    raw_entities JSONB DEFAULT '{}'::jsonb,
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
