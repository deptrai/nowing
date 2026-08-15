# Technical Research — Cổng Thông Tin Đấu Thầu Quốc Gia (`muasamcong.mpi.gov.vn`)

**Ngày nghiên cứu:** 2026-08-15  
**Tác giả:** BMAD Technical Research Team  
**Mục tiêu:** Khảo sát chi tiết cấu trúc hệ thống Mạng Đấu thầu Quốc gia mới (e-GP v2.0), phân tích phương thức cào Thông Báo Mời Thầu (TBMT), Kết Quả Lựa Chọn Nhà Thầu (KQLCNT), giải pháp tải và bóc tách tài liệu đính kèm (HSMT/PDF) cho Nowing Vector Search & Alert Engine (Epic 23).

---

## 1. Tổng quan Kiến trúc e-GP v2.0

Hệ thống Mạng Đấu thầu Quốc gia (`https://muasamcong.mpi.gov.vn`) vận hành trên kiến trúc Single Page Application (SPA) với backend REST microservices, bảo mật bằng WAF/Cloudflare và ký số qua VNeGP Client Agent.

### Các phân hệ chính:
1. **Phân hệ Tra cứu Thông báo Mời thầu (TBMT):** Cung cấp toàn bộ thông tin các gói thầu đang mở, thời gian đóng/mở thầu, bên mời thầu, chủ đầu tư, giá trị dự toán và lĩnh vực (Xây lắp, Mua sắm hàng hóa, Dịch vụ tư vấn, Phi tư vấn).
2. **Phân hệ Kết quả Lựa chọn Nhà thầu (KQLCNT):** Cung cấp danh tính nhà thầu trúng thầu, giá trúng thầu, tỷ lệ tiết kiệm ngân sách, danh sách nhà thầu trượt thầu và lý do trượt.
3. **Phân hệ Kế hoạch Lựa chọn Nhà thầu (KHLCNT):** Tín hiệu đầu nguồn về các dự án đầu tư công chuẩn bị ra thầu trong 3–12 tháng tới (Lead cực mạnh cho B2B).

---

## 2. Phân tích Endpoints & Giao thức Thu thập (Ingress Architecture)

### 2.1. Tra cứu Thông báo Mời thầu (TBMT Search API)

* **Method:** `POST`
* **URL:** `https://muasamcong.mpi.gov.vn/api/v1/tender/notice/search` (hoặc internal portal API `/services/portal-bid/tbmt/search`)
* **Payload (JSON):**
```json
{
  "page": 0,
  "size": 50,
  "sort": "publicDate,desc",
  "searchKeyword": "",
  "bidField": "ALL",
  "isBidding": true,
  "bidType": "PUBLIC",
  "fromDate": "2026-08-01T00:00:00.000Z",
  "toDate": "2026-08-15T23:59:59.999Z"
}
```
* **Headers Bắt buộc:**
  * `User-Agent`: Chrome/128+ Standard Windows/Mac header.
  * `Accept`: `application/json, text/plain, */*`
  * `Referer`: `https://muasamcong.mpi.gov.vn/`
  * `Origin`: `https://muasamcong.mpi.gov.vn`
* **Response Data Fields:**
  * `bidNo` / `bidCode`: Mã định danh thông báo mời thầu (VD: `IB2400123456`).
  * `bidName`: Tên gói thầu.
  * `investorName`: Tên chủ đầu tư.
  * `procuringEntityName`: Bên mời thầu.
  * `bidPrice`: Giá gói thầu (VNĐ).
  * `bidOpenDate`: Thời điểm mở thầu.
  * `bidCloseDate`: Thời điểm đóng thầu.
  * `location`: Địa điểm thực hiện (Tỉnh/Thành phố).
  * `documentAttachmentIds`: Danh sách ID tài liệu HSMT.

### 2.2. Chi tiết Gói thầu & Tải Hồ sơ Mời Thầu (E-HSMT)

* **Detail URL:** `https://muasamcong.mpi.gov.vn/api/v1/tender/notice/detail/{bidNo}`
* **File Download URL:** `https://muasamcong.mpi.gov.vn/api/v1/tender/attachment/download/{attachmentId}`
* **Định dạng file:** `.pdf`, `.docx`, `.xlsx`, `.zip`.
* **Xử lý tài liệu lớn:** Với các file HSMT lớn (50MB–200MB), worker sử dụng Celery task bất đồng bộ tải trực tiếp vào S3, sau đó dùng `app/services/okf/` (OCR + Text Extraction) để phân tích bảng tiên lượng, tiêu chuẩn đánh giá năng lực tài chính và kinh nghiệm nhân sự.

---

## 3. Thách thức Anti-Bot & Giải pháp Kỹ thuật

| Thách thức | Chi tiết | Giải pháp Kỹ thuật cho Nowing |
| :--- | :--- | :--- |
| **WAF / Rate Limiting** | Giới hạn 30 req/phút từ 1 IP; IP lạ hoặc tần suất cao sẽ bị CAPTCHA hoặc HTTP 403. | Sử dụng Rotating Datacenter/ISP Proxies Việt Nam (VNPT, Viettel) kết hợp `ScraperPlatformAccountRotator` với Token-Bucket 15 req/phút. |
| **Session Cookies (XSRF/JWT)** | Một số endpoint yêu cầu CSRF token sinh ra từ trang chủ. | Gửi request `GET /` khởi tạo session cookie trước khi query POST API. |
| **File HSMT Mã hóa / Yêu cầu Client** | Một số file thầu mật hoặc bảo mật yêu cầu VNeGP Client Agent. | Với 95% gói thầu công khai, file đính kèm là công khai không cần token ký số; bỏ qua 5% gói mật. |

---

## 4. Mô hình Dữ liệu Lưu trữ (PostgreSQL DDL)

```sql
CREATE TABLE IF NOT EXISTS procurement_tenders (
    id BIGSERIAL PRIMARY KEY,
    bid_code VARCHAR(100) NOT NULL UNIQUE,
    bid_name TEXT NOT NULL,
    investor_name TEXT,
    procuring_entity TEXT,
    bid_price NUMERIC(18, 2),
    procurement_field VARCHAR(100),
    funding_source TEXT,
    bid_open_date TIMESTAMPTZ,
    bid_close_date TIMESTAMPTZ,
    location VARCHAR(255),
    document_urls TEXT[],
    raw_specs JSONB DEFAULT '{}'::jsonb,
    summary_md TEXT,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_procurement_tenders_code ON procurement_tenders(bid_code);
CREATE INDEX IF NOT EXISTS idx_procurement_tenders_close_date ON procurement_tenders(bid_close_date);
CREATE INDEX IF NOT EXISTS idx_procurement_tenders_gin_specs ON procurement_tenders USING gin (raw_specs);
CREATE INDEX IF NOT EXISTS idx_procurement_tenders_embedding_hnsw ON procurement_tenders USING hnsw (embedding vector_cosine_ops);
```

---

## 5. Tích hợp Hệ sinh thái Nowing

1. **Alert Engine (Saved Searches):** Cho phép doanh nghiệp tạo AlertRule: *"Báo cho tôi khi có gói thầu Xây lắp tại Hà Nội giá trị > 20 tỷ trước ngày đóng thầu 5 ngày"*.
2. **AI Agent Tool (`procurement_search_tenders`):** Cho phép người dùng hỏi AI: *"Tìm các gói thầu phần mềm y tế đang mở thầu trong tháng 8/2026 và tóm tắt yêu cầu chứng chỉ ISO"*.
3. **ChainLens Vector Feed:** Chuyển đổi tóm tắt gói thầu thành knowledge chunks đưa vào `chainlens-research`.
