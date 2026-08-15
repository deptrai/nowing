# Báo Cáo Thẩm Định Code Review (Adversarial Code Review Report)

**Dự án:** Nowing Platform  
**Story được Review:** [Story 21.9: Executive Decision Maker Mapping & B2B Lead Outreach](file:///Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/21-9-executive-decision-maker-mapping-b2b-outreach.md)  
**Ngày thực hiện:** 2026-08-15  
**Phương pháp:** 3-Layer Adversarial Code Review (Acceptance Auditor, Blind Hunter, Edge Case Hunter)  
**Kết luận:** 🟢 **`APPROVED / CLEAN REVIEW` (VƯỢT QUA KIỂM DUYỆT 100%)**

---

## 🔍 1. KẾT QUẢ ĐỐI CHIẾU 3 LỚP HUNTERS

### 🕵️ Layer 1: Acceptance Auditor (Thẩm định AC & Invariants)
* **AC-1 (SERP Dorking Public Leadership Ingress):** `build_serp_dork_query` và `ExecutiveDorker` tìm kiếm chính xác hồ sơ lãnh đạo trên LinkedIn qua Google/Bing/DDG mà không yêu cầu tài khoản LinkedIn (AD-LI-4). `PASS`.
* **AC-2 (Corporate Email Prediction & DNS MX Check):** `predict_executive_email()` sinh 9 mẫu email doanh nghiệp chuẩn, bóc tách họ tên tiếng Việt (khử dấu tiếng Việt `Đ/đ`, xử lý danh xưng `ông/bà/TS/ThS`) và kiểm tra bản ghi DNS MX an toàn (AD-LI-7). `PASS`.
* **AC-3 (B2B Outreach Generator with Buying Signals):** `B2BOutreachService` tự động soạn email chào hàng dựa trên các tín hiệu mua hàng (`HIRING_SPIKE`, `TENDER_WIN`, `FUNDING_ROUND`). `PASS`.
* **AC-4 (AI Agent Capability & MCP Tool):** Đăng ký capability `b2b.decision_makers` và tool `nowing_b2b_find_decision_makers` trong `MCP_TOOL_CATALOG`. `PASS`.
* **Invariants AD-LI-1 đến AD-LI-7:** Tuân thủ 100%.

---

### 🕵️ Layer 2: Blind Hunter (Bảo mật, SSRF, Concurrency)
* **SSRF Protection:** `check_domain_mx` thực hiện chuẩn hóa và tách host nghiêm ngặt, chặn đứng nguy cơ SSRF qua DNS lookup. `PASS`.
* **Resource Leaks:** Toàn bộ phiên `httpx.AsyncClient` đều được bọc trong `try...finally: if should_close: await client.aclose()`. `PASS`.
* **SQL Injection:** Model `CompanyDecisionMaker` sử dụng SQLAlchemy ORM Parameterized queries với unique index `(company_id, linkedin_slug)`. `PASS`.

---

### 🕵️ Layer 3: Edge Case Hunter (Xử lý chuỗi, Tên Tiếng Việt & Lỗi DNS)
* **Tên tiếng Việt phức tạp (3-5 từ):** `normalize_name_for_email("Nguyễn Thị Thu Hà")` bóc tách đúng họ `nguyen`, tên `ha`, sinh `ha.nguyen@domain.com` và `nguyen.ha@domain.com`. `PASS`.
* **Ký tự đặc thù tiếng Việt "Đ/đ":** Khử chính xác thành "D/d" trước khi chuẩn hóa NFD. `PASS`.
* **Tên miền không tồn tại (NXDOMAIN) / Timeout DNS:** DNS resolver có timeout 3.0s, tự động trả về `mx_valid=False` và gán điểm tin cậy 0.40 an toàn không gây sập ứng dụng. `PASS`.

---

## 🧪 2. BẰNG CHỨNG KIỂM THỬ THỰC TẾ

```text
============================= test session starts ==============================
rootdir: /Users/luisphan/Documents/GitHub/nowing/nowing_backend
collected 14 items

tests/unit/proprietary/platforms/linkedin/test_email_predictor.py ...... [ 42%]
tests/unit/proprietary/platforms/linkedin/test_executive_dorker.py ......[ 85%]
tests/unit/capabilities/test_b2b_decision_makers.py ..                   [100%]

======================== 14 passed in 3.03s ========================
```

* **Linter:** `uv run ruff check` $\rightarrow$ **`All checks passed!`** (0 errors).

---

## 🏁 3. QUYẾT ĐỊNH TRIỂN KHAI
* **Trạng thái Story:** Xác nhận **`done`** ✅ trong [`sprint-status.yaml`](file:///Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/sprint-status.yaml).
