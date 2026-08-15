# Story 21.9: Executive Decision Maker Mapping & B2B Lead Outreach

Status: ready-for-dev

<!-- Note: Governed by architecture-linkedin-b2b-2026-08-15 (AD-LI-1 to AD-LI-7) -->

## Story

As an enterprise sales team or SaaS founder,
I want to identify C-Level executives and HR leaders of expanding companies,
So that I can initiate personalized outreach and CRM synchronization.

## Acceptance Criteria

1. **Given** a target company name or domain, **When** `ExecutiveSearchService` is triggered, **Then** it generates privacy-compliant Google/Bing SERP dork queries (`site:linkedin.com/in/ "{company}" ("CEO" OR "Founder" OR "HR Director" OR "CFO")`) and fetches top public leadership profiles without requiring authenticated LinkedIn scraping.
2. **Given** raw search results, **When** parsed by `ExecutiveParser`, **Then** executive profiles (Full Name, Title, LinkedIn URL slug, Inferred Business Email pattern `first.last@{domain}`) are extracted and stored into `company_decision_makers` table with unique constraint `(company_id, linkedin_slug)`.
3. **Given** identified executives and associated buying signals (e.g. recent headcount spike from Story 12.10 or active bidding tender from Story 16.5), **When** a user clicks "Generate Outreach Draft", **Then** the LLM drafts a highly personalized, contextual B2B sales email referencing the company's specific growth signals.
4. **Given** an AI Agent session, **When** invoking `b2b_find_decision_makers(company_name, role_keyword)`, **Then** the agent returns verified executive profiles and contact suggestions.

## Tasks / Subtasks

- [ ] Task 1: Database Schema for Decision Makers (AC: 2)
  - [ ] 1.1 Tạo bảng `company_decision_makers` (`id`, `company_id`, `full_name`, `title`, `department`, `linkedin_url`, `linkedin_slug`, `email_prediction`, `confidence_score`, `verified_at`, `created_at`, `CONSTRAINT uq_company_executive UNIQUE (company_id, linkedin_slug)`).
  - [ ] 1.2 Thiết lập khóa ngoại liên kết tới bảng `companies` và chỉ mục `idx_executives_company_title`.
- [ ] Task 2: Privacy-Compliant SERP Dorking Engine (AC: 1, 2)
  - [ ] 2.1 Xây dựng `ExecutiveDorker` tại `nowing_backend/app/proprietary/platforms/linkedin/executive_dorker.py`.
  - [ ] 2.2 Xây dựng hàm tạo query dorking an toàn: `build_serp_dork_query(company_name, roles=['CEO', 'Founder', 'HR Director', 'CTO'])`.
  - [ ] 2.3 Phân tích snippet kết quả tìm kiếm với `selectolax` để bóc tách Tên, Chức vụ và URL profile.
- [ ] Task 3: B2B Email Predictor & Pattern Matcher (AC: 2)
  - [ ] 3.1 Xây dựng `EmailPatternGenerator` suy đoán email theo các định dạng phổ biến (`first.last@domain.com`, `first@domain.com`).
  - [ ] 3.2 Tích hợp kiểm tra MX Record DNS của domain đích.
- [ ] Task 4: AI Contextual Outreach Draft Engine (AC: 3)
  - [ ] 4.1 Xây dựng `B2BOutreachService` tại `nowing_backend/app/services/outreach_service.py`.
  - [ ] 4.2 Nhận diện tín hiệu mua hàng (Headcount spike, Tender trúng thầu) để tạo prompt cá nhân hóa cho email.
- [ ] Task 5: AI Agent Capability & Tools (AC: 4)
  - [ ] 5.1 Đăng ký Capability `b2b.decision_makers` trong `app/capabilities/b2b/`.
  - [ ] 5.2 Định nghĩa Agent Tool `b2b_find_decision_makers` phục vụ AI Agent tra cứu.
- [ ] Task 6: Unit & Integration Tests (AC: 1-4)
  - [ ] 6.1 `tests/unit/platforms/test_serp_dork_builder.py` (Kiểm tra format query và escaping ký tự đặc biệt).
  - [ ] 6.2 `tests/unit/services/test_email_pattern_predictor.py` (Kiểm tra thuật toán sinh email doanh nghiệp).
  - [ ] 6.3 `tests/integration/platforms/test_executive_dorking.py` (Mock SERP HTML $\rightarrow$ DB mapping).

## Dev Notes

- **Architecture Invariants:** Tuân thủ AD-LI-1, AD-LI-3, AD-LI-6 trong `architecture-linkedin-b2b-2026-08-15/ARCHITECTURE-SPINE.md`.
- **Anti-Bot Strategy:** Không đăng nhập tài khoản LinkedIn trực tiếp; khai thác qua Public Google/Bing SERP Dorking để loại trừ rủi ro bị khóa tài khoản người dùng.
- **Dependencies:** `selectolax>=0.3.21`, `httpx>=0.28.1`, `dnspython>=2.6.1`.

### References
- [Architecture Spine: architecture-linkedin-b2b-2026-08-15/ARCHITECTURE-SPINE.md]
- [UX Contract: ux-contract-scrapers-expansion-and-lead-intelligence.md#U4]
