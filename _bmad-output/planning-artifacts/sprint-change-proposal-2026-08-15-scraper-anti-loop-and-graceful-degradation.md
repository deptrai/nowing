# Sprint Change Proposal: Scraper Anti-Loop & Graceful Degradation Invariant (AD-19.1)

- **Date:** 2026-08-15
- **Author:** Codex Architect & Developer Agent
- **Status:** PROPOSED (Awaiting Founder Approval)
- **Target Release:** Sprint Execution / Multi-Agent Chat & Scraper Engine

---

## 1. Issue Summary

### 1.1 Problem Statement
Trong quá trình kiểm thử E2E trực tiếp cho **Story 21.9** (Executive Decision Maker Mapping & B2B Lead Outreach), khi người dùng gửi prompt yêu cầu tìm lãnh đạo và soạn email chào hàng B2B, Subagent `google_search` bị Google chặn bot trên môi trường local (`no SERP HTML` do chưa có residential proxy).

Do thiếu cơ chế chặn lặp (Anti-Loop Guard / Early Fail-Fast) và chỉ dẫn trong `output_contract_base.md` vô tình thúc đẩy retry (*"re-running with adjusted parameters, execute it now and report the improved result"*), subagent đã tự động thử lại 8 lần liên tiếp với các biến thể từ khóa khác nhau. Quá trình này tiêu tốn **83 giây và 27 vòng gọi LLM**, làm cạn kiệt ngân sách lượt gọi của turn chat. Hậu quả là luồng stream bị đóng lại mà không kịp sinh văn bản trả lời cho người dùng (`text=0`).

### 1.2 Root Cause Analysis
1. **Thiếu Anti-Loop Cap trong Subagent System Prompts:** Toàn bộ 22 subagents trong `nowing_backend/app/agents/chat/multi_agent_chat/subagents/builtins/` kế thừa `output_contract_base.md` nhưng không có quy tắc chặn trần retry khi scraper bị 0 kết quả hoặc bị chặn bot.
2. **Thiếu Graceful Degradation Invariant cho Scraper Tools:** Mặc dù Story 9.1a đã chuẩn hóa cơ chế degradation cho `chainlens.research`, kiến trúc chung chưa có một Architectural Decision (AD) áp dụng bất biến này cho **toàn bộ Scraper capabilities & Subagents**.
3. **Môi trường Zero-Proxy:** Ở môi trường local / self-host không có proxy pool, việc bị chặn bot là trạng thái vận hành bình thường (expected runtime state) và hệ thống phải fail-soft & fallback thông minh thay vì retry vô vọng.

---

## 2. Impact Analysis

### 2.1 Epic & Story Impact
- **Epic 9 (Deep Research):** Giữ nguyên tuân thủ Story 9.1a & 9.1b.
- **Epic 10 (Platform Scrapers - Batdongsan, CafeF, Vietstock, TikTok, etc.):** Toàn bộ 15+ scraper subagents sẽ được bảo vệ bởi Anti-Loop Guard.
- **Epic 20 (Scraper Ingest & Chunks):** Không thay đổi.
- **Epic 21 (Lead Intelligence & Outreach):** Story 21.9 và các story tiếp theo sẽ luôn hoàn tất bản nháp email và danh bạ lãnh đạo kể cả khi live scraping trả về 0 kết quả.

### 2.2 Architectural Impact
- Bổ sung **`AD-19.1`** vào [`ARCHITECTURE-SPINE.md`](file:///Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md) để cố định 4 bất biến thiết kế (4 Invariants) cho tất cả scraper hiện tại và tương lai.

---

## 3. Recommended Approach: Direct Adjustment + Architecture Hardening

### 3.1 Bổ sung AD-19.1 vào `ARCHITECTURE-SPINE.md`

```markdown
### AD-19.1 — Scraper Anti-Loop & Graceful Degradation Invariant (Universal Scraper & Subagent Resilience)
- **Binds:** FR-24, FR-38, FR-63..67, NFR-9; Epic 9, Epic 10, Epic 20, Epic 21.
- **Prevents:** Khi bất kỳ scraper nào (Google Search, LinkedIn, Batdongsan, Vietstock, TikTok...) chạy ở môi trường không có proxy (Zero-Proxy) hoặc gặp anti-bot walling (no SERP HTML, 403, 429, CAPTCHA), subagent rơi vào vòng lặp retry vô tận làm cạn turn budget và khiến Main Agent kết thúc với text rỗng (text=0).
- **Rule (4 Bất Biến Cốt Lõi):**
  1. **Zero-Proxy & Anti-Bot Tolerance:** Có proxy (`PROXY_URL`/`PROXY_URLS`) thì tối ưu tỷ lệ thành công, nhưng **không có proxy hoặc bị chặn IP là trạng thái vận hành bình thường**. Scraper không được crash 500 hay treo vòng lặp.
  2. **Subagent Anti-Loop Ceiling:** Áp dụng trần tối đa **1 lần retry** khi tool trả về 0 kết quả hoặc bị chặn bot. Ngay sau đó, subagent PHẢI trả về `status: "blocked"` hoặc `status: "partial"` kèm `next_step` và `evidence: {"findings": [], "sources": []}`. CẤM thử lại liên tiếp > 1 lần.
  3. **Main-Agent Parametric & Knowledge Fallback:** Khi subagent báo `blocked`/`partial`, Main Agent supervisor **tuyệt đối không kết thúc lượt chat với text=0**. Supervisor PHẢI tự động chuyển sang tổng hợp câu trả lời bằng Parametric Memory + Workspace Knowledge Base, nêu rõ giới hạn dữ liệu mạng một cách trung thực cho người dùng.
  4. **Universal Contract cho mọi Scraper tương lai:** Mọi capability scraper hoặc subagent mới tích hợp vào Nowing BẮT BUỘC tuân thủ `output_contract_base.md` và anti-loop failure policy.
```

---

## 4. Detailed Change Proposals (Code & Prompt Edits)

### 4.1 Cập nhật `output_contract_base.md` (Shared Snippet cho 22 Subagents)
- **File:** `nowing_backend/app/agents/chat/multi_agent_chat/subagents/shared/snippets/output_contract_base.md`
- **Thay đổi:** Thêm ràng buộc Anti-Loop Ceiling (tối đa 1 retry khi tool rỗng/lỗi).

### 4.2 Cập nhật `google_search` Subagent System Prompt
- **File:** `nowing_backend/app/agents/chat/multi_agent_chat/subagents/builtins/google_search/system_prompt.md`
- **Thay đổi:** Bổ sung quy tắc Fast-Fail khi gặp `no SERP HTML` / Anti-Bot block.

### 4.3 Cập nhật Main Agent System Prompt (`output_format.md` / `core_behavior.md`)
- **File:** `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/core_behavior.md`
- **Thay đổi:** Bổ sung quy tắc bắt buộc sinh nội dung trả lời (non-empty text response) khi các subagent gặp `status=blocked` hoặc `status=partial`.

---

## 5. Implementation Handoff & Success Criteria

- **Scope:** Minor to Moderate (Direct Implementation by Developer Agent).
- **Deliverables:**
  1. Cập nhật `ARCHITECTURE-SPINE.md` với `AD-19.1`.
  2. Cập nhật `output_contract_base.md` & `google_search/system_prompt.md`.
  3. Kiểm thử lại luồng Chat trên Playwright: Gửi lại prompt tìm kiếm lãnh đạo FPT Software $\rightarrow$ Agent phải hoàn tất câu trả lời và soạn bản nháp Email B2B trôi chảy trong vòng < 15 giây mà không bị treo hay loop.
