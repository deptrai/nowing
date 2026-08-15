# Báo Cáo Thẩm Định Code Review (Adversarial Code Review Report)

**Dự án:** Nowing Platform  
**Story được Review:** [Story 12.10: LinkedIn Public Guest Jobs & Headcount Growth Signals](file:///Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/12-10-linkedin-public-guest-jobs-headcount-signals.md)  
**Ngày thực hiện:** 2026-08-15  
**Phương pháp:** 3-Layer Adversarial Code Review (Acceptance Auditor, Blind Hunter, Edge Case Hunter)  
**Kết luận:** 🟢 **`APPROVED / CLEAN REVIEW` (VƯỢT QUA KIỂM DUYỆT 100%)**

---

## 🔍 1. KẾT QUẢ ĐỐI CHIẾU 3 LỚP HUNTERS

### 🕵️ Layer 1: Acceptance Auditor (Thẩm định AC & Invariants)
* **AC-1 (LinkedIn Public Guest Jobs API Ingress):** `LinkedInGuestJobScraper` thu thập tin tuyển dụng qua Guest Ingress endpoint `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search` và bóc tách HTML chi tiết qua `selectolax` mà không cần đăng nhập tài khoản (AD-LI-1: Zero-Login Invariant). `PASS`.
* **AC-2 (PostgreSQL Idempotent Storage):** Hàm `persist_linkedin_jobs` thực hiện PostgreSQL Idempotent UPSERT (`ON CONFLICT DO UPDATE`) trên `linkedin_jobs` theo `job_id` và `linkedin_companies` theo `company_slug` (AD-LI-5). `PASS`.
* **AC-3 (Hiring Velocity & Intent Flag $\ge 20\%$):** `calculate_hiring_velocity` và `HiringVelocityCalculator` tính toán tốc độ tăng trưởng tuyển dụng 30 ngày và tự động gán cờ `high_buying_intent = True` khi tốc độ tăng $\ge 20\%$ và có ít nhất 1 tin tuyển dụng mới mở (AD-LI-3). `PASS`.
* **AC-4 (Capabilities & MCP Tools):** Đăng ký capability `recruitment.linkedin_jobs` và tool `nowing_recruitment_search_linkedin_jobs` vào `MCP_TOOL_CATALOG`. `PASS`.
* **Invariants AD-LI-1 đến AD-LI-7:** Tuân thủ 100%.

---

### 🕵️ Layer 2: Blind Hunter (Bảo mật, Resource Leaks & Anti-Bot)
* **Resource Cleanup:** Toàn bộ phiên `httpx.AsyncClient` trong scraper đều được đóng an toàn bằng `try...finally: await client.aclose()`. `PASS`.
* **Rate-Limit & Anti-Bot Jitter:** Áp dụng random human jitter 1.5s - 3.5s giữa các trang và xử lý mã lỗi HTTP 429/403. `PASS`.

---

### 🕵️ Layer 3: Edge Case Hunter (Xử lý chuỗi, Công ty mới & Dữ liệu rỗng)
* **Công ty mới không có lịch sử tuyển dụng trong 30 ngày trước:** Công thức chia bảo vệ chống chia cho 0 `max(prior, 1)` và tự động tính `velocity = float(jobs_last_30d)`. `PASS`.
* **Trích xuất ngày đăng tương đối ("2 weeks ago", "1 month ago"):** Hàm parse ngày hỗ trợ chuẩn hóa thời gian chính xác về mốc UTC datetime. `PASS`.

---

## 🧪 2. BẰNG CHỨNG KIỂM THỬ THỰC TẾ

```text
============================= test session starts ==============================
rootdir: /Users/luisphan/Documents/GitHub/nowing/nowing_backend
collected 12 items

tests/unit/proprietary/platforms/linkedin/test_guest_job_scraper.py ..... [ 41%]
tests/unit/proprietary/platforms/linkedin/test_velocity_calculator.py ... [ 66%]
tests/unit/capabilities/test_linkedin_jobs_capabilities.py ....          [100%]

======================== 12 passed in 1.27s ========================
```

* **Linter:** `uv run ruff check` $\rightarrow$ **`All checks passed!`** (0 errors).

---

## 🏁 3. QUYẾT ĐỊNH TRIỂN KHAI
* **Trạng thái Story:** Xác nhận **`done`** ✅ trong [`sprint-status.yaml`](file:///Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/sprint-status.yaml).
