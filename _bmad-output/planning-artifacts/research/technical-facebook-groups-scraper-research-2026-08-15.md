# Technical Research — Facebook Groups & Fanpages Scraper

**Ngày nghiên cứu:** 2026-08-15  
**Tác giả:** BMAD Technical Research Team  
**Mục tiêu:** Khảo sát các kỹ thuật thu thập dữ liệu bài viết, bình luận, số điện thoại từ Facebook Groups & Fanpages công khai tại Việt Nam năm 2026 mà không làm khóa tài khoản, phục vụ cho Epic 21A (Social Lead Generation) và Alert Engine.

---

## 1. Tổng quan Thách thức Facebook Scraping năm 2026

Facebook (Meta) áp dụng các biện pháp phòng thủ bot nghiêm ngặt nhất thế giới:
1. **Dynamic Infinite Scroll (JavaScript Virtual DOM):** Không có HTML tĩnh dạng `<table>` hay `<ul>`; bài viết chỉ render khi người dùng cuộn và tương tác.
2. **Behavioral AI Detection & Checkpoints:** Phân tích tốc độ cuộn, con trỏ chuột, vân tay trình duyệt (Canvas/WebGL/TLS fingerprint) và lịch sử hành vi để yêu cầu xác thực khuôn mặt / 2FA / checkpoint 956/282.
3. **Deprecated mbasic:** Giao diện `mbasic.facebook.com` đã bị hạn chế tối đa hoặc buộc đăng nhập.

---

## 2. Chiến lược Thu thập Hai Làn (Hybrid Ingestion Strategy)

Để đảm bảo vừa an toàn cho tài khoản vừa đạt hiệu năng cao, Nowing áp dụng mô hình Hai Làn tương tự Telegram:

```
                                  [ Yêu cầu Cào Facebook ]
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
             [ Làn 1: Public Fast Path ]                 [ Làn 2: Deep Group Stream ]
          (Fanpage & Kênh Công khai)                     (Nhóm Kín / Thảo luận / SĐT)
                       │                                           │
         Puppeteer/Playwright Stealth                 Cookie Session Pool (Via xactions)
             (Headless + Tor/Proxy)                   (Sticky SOCKS5 Residential Proxy)
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             ▼
                                 [ Entity Extractor Engine ]
                                  (SĐT, Giá BĐS, Intent tag)
                                             │
                                             ▼
                             [ PostgreSQL + Redis Stream Buffer ]
```

### Làn 1: Public Fanpages & Public Groups Fast Path (Playwright Stealth)
* Sử dụng `playwright` với plugin `stealth` và fingerprinting giả lập iPhone/Android hoặc Chrome desktop thật.
* Không cần đăng nhập tài khoản chính; thu thập các bài viết công khai trên Fanpage tin tức, bất động sản, việc làm.
* Điều hướng trực tiếp: `https://www.facebook.com/{page_name}` hoặc `https://m.facebook.com/{page_name}`.

### Làn 2: Deep Group Stream & Comments (Cookie Session Pool qua xactions)
* Tận dụng hạ tầng MCP server `xactions` hiện có của Nowing (`x_facebook_group_posts`, `x_facebook_group_comments`, `x_facebook_posts`).
* Lưu trữ cookie Facebook dạng mã hóa AES-256 trong bảng `scraper_platform_accounts` (`platform='facebook'`).
* Ghép cố định 1-to-1 giữa mỗi tài khoản Facebook phụ (nick clone/nuôi) với một Sticky Residential Proxy tại Việt Nam (`socks5h://`).
* Giới hạn Token Bucket: Tối đa 20 requests/giờ/tài khoản, có human-like delay (3–8 giây ngẫu nhiên giữa các lần cuộn trang).

---

## 3. Trích xuất Thực thể & Phân loại Ý định (Entity Extraction & Intent Classification)

Bài viết trên nhóm Facebook thường có cú pháp tự do. Pipeline xử lý ngôn ngữ tự nhiên:
1. **Regex Phone Extraction:** Bóc tách các dạng số điện thoại VN: `09xx...`, `03xx...`, `07xx...`, `08xx...`, `(024)...`, các biến thể cố tình viết né kiểm duyệt như `o9.12.345.678`, `không chín một hai...`.
2. **Intent Tagging:** AI Router phân loại bài viết:
   * `bds_sell`: Bán nhà/đất.
   * `bds_buy`: Cần mua / tìm nhà.
   * `job_hiring`: Tuyển dụng.
   * `job_seeking`: Tìm việc.
3. **Price Normalization:** Chuẩn hóa giá: `3 tỷ 2`, `850tr`, `15 tr/tháng`, `thỏa thuận`.

---

## 4. Mô hình Dữ liệu Lưu trữ (PostgreSQL DDL)

```sql
CREATE TABLE IF NOT EXISTS facebook_groups (
    id BIGSERIAL PRIMARY KEY,
    group_id VARCHAR(100) NOT NULL UNIQUE,
    group_name TEXT NOT NULL,
    group_url TEXT NOT NULL,
    category VARCHAR(50) NOT NULL, -- 'bds', 'recruitment', 'crypto', 'ecommerce'
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    realtime_stream BOOLEAN NOT NULL DEFAULT FALSE,
    last_scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS facebook_posts (
    id BIGSERIAL PRIMARY KEY,
    group_id BIGINT REFERENCES facebook_groups(id) ON DELETE CASCADE,
    post_id VARCHAR(100) NOT NULL,
    author_name TEXT,
    author_id VARCHAR(100),
    post_url TEXT,
    content TEXT,
    intent_tag VARCHAR(50), -- 'sell', 'buy', 'hiring', 'seeking', 'other'
    reactions_count INT DEFAULT 0,
    comments_count INT DEFAULT 0,
    raw_entities JSONB DEFAULT '{}'::jsonb,
    media_urls TEXT[],
    embedding vector(1536),
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_facebook_group_post UNIQUE (group_id, post_id)
);

CREATE INDEX IF NOT EXISTS idx_facebook_posts_group_published ON facebook_posts(group_id, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_facebook_posts_intent ON facebook_posts(intent_tag);
CREATE INDEX IF NOT EXISTS idx_facebook_posts_gin_entities ON facebook_posts USING gin (raw_entities);
CREATE INDEX IF NOT EXISTS idx_facebook_posts_embedding_hnsw ON facebook_posts USING hnsw (embedding vector_cosine_ops);
```

---

## 5. Tích hợp Hệ sinh thái Nowing

1. **Epic 21 (Lead Gen Outreach):** Bài viết mua nhà đất hoặc tuyển dụng ngay lập tức trở thành Lead trong CRM kèm số điện thoại liên hệ.
2. **Alert Engine Trigger:** Khi có bài đăng mới khớp từ khóa *"nhà ngõ ô tô Cầu Giấy"* $\rightarrow$ Bắn thông báo Telegram/Email cho người dùng trong vòng $\le 5$ giây.
3. **AI Chat Search:** Công cụ `facebook_search_group_posts(group, keyword)` cho phép AI trả lời trực tiếp các câu hỏi về thị trường chợ đen/thứ cấp.
