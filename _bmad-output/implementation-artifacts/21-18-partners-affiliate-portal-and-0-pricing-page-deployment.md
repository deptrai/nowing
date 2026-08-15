---
baseline_commit: 591bc6a1672e5ec1f8ffe0afdfdcbb35f8f1a24d
---

# Story 21.18: Partners Affiliate Portal & $0 Pricing Page Deployment

Status: ready-for-dev

<!-- Note: Governed by epics.md (FR-88, AD-42, UX-Contract-Landing-Page) & DESIGN.md, EXPERIENCE.md -->

## Story

As an affiliate partner, marketing agency, or B2B growth freelancer,
I want a high-converting `/pricing` page with clear $0 Free & Pay-as-you-go tiers, and a dedicated `/partners` affiliate portal with 30-day cookie tracking, a 15% lifetime recurring commission ledger, and instant VietQR/Stripe payout requests,
So that I can confidently refer clients to Nowing, track my referrals and earnings in real time, and receive seamless automated commission payouts.

## Acceptance Criteria

1. **Given** navigation to `/pricing`, **When** the page renders, **Then** it presents the modernized Origami Mint Green theme (`#10B981`, `#059669`, `#ECFDF5`, Sọc Caro Grid Paper background texture `20px x 20px`, typography trio: `Instrument Serif`, `Plus Jakarta Sans`, `JetBrains Mono`) with 3 distinct tiers:
   - **$0 FREE TIER (Open-Core & Self-Host / Starter Cloud):** $0/mo, Unlimited AI Chat, BYOK support, Sequencer, CSV Export, $5 starter cloud credit balance.
   - **PAY AS YOU GO (Unified Credit Wallet):** $0 subscription, 100% usage-based credits ($1 = 1,000,000 micros). Transparent unit rates: Phone Unlock (~$0.05 / 5 credits), Deep Research (~$0.02 - $0.05), Web Scrapers/Crawlers ($0.001 - $0.005/item, failed calls never billed), Premium LLMs at provider cost, optional Auto-Reload ($10, $25, $50, $100).
   - **ENTERPRISE TIER:** Custom scraper IP pools, On-prem/VPC deployment, Custom connectors, SSO/SAML, 99.9% SLA, Dedicated account manager.
   - **Interactive Credit Calculator:** Dynamic slider estimating Monthly Leads / Scrapes / Research runs with instant USD & VND conversion ($1 = 25,400 VND).
   - **Feature Comparison Matrix & FAQ:** Exhaustive capability breakdown and structured SEO `SoftwareApplication` + `FAQPage` JSON-LD metadata.

2. **Given** navigation to `/partners` (Public Affiliate Landing Page), **When** viewed, **Then** it renders:
   - Value Proposition Hero: "Nhận 15% hoa hồng trọn đời (Lifetime Recurring Commission) khi giới thiệu doanh nghiệp & chuyên gia sử dụng Nowing".
   - Target Persona Cards: Marketing Agencies, B2B Growth Freelancers, Giảng viên / Chuyên gia BĐS & Tuyển dụng, Tech KOLs.
   - Interactive Commission Earnings Calculator: E.g., 20 khách hàng $\times$ $100/tháng = $300/tháng ($7,620,000 VND/tháng) thu nhập thụ động bền vững.
   - 1-Click "Đăng ký làm Đối tác" CTA directing to instant partner onboarding.

3. **Given** an incoming visitor with referral parameter (e.g., `https://nowing.net/?ref=GROWTH_AGENCY` or `https://nowing.net/pricing?ref=GROWTH_AGENCY`), **When** any public page loads, **Then**:
   - The frontend sets a secure cookie `nowing_ref=GROWTH_AGENCY` with `maxAge: 30 * 86400` (30 days), `path: '/'`, `sameSite: 'lax'`.
   - Subsequent page navigations preserve the attribution cookie.

4. **Given** a new user registration via email/password or Google OAuth, **When** `UserManager.on_after_register` executes, **Then**:
   - The backend checks for the `nowing_ref` cookie in the request headers.
   - If a valid, active `AffiliatePartner` matches the `referral_code` and `user.id != partner.user_id` (anti-self-referral check), it automatically creates a `PartnerReferral` record linking the new user to the partner.

5. **Given** an authenticated user accessing the Affiliate Portal (`/partners/dashboard` or `/dashboard/[workspace_id]/partners`), **When** viewed, **Then** it displays:
   - **Summary Stats Cards:** Clicks tracked, Total Referrals, Active Paying Customers, Total Gross Revenue Generated, Total Commission Earned (15%), Available Payout Balance, Total Paid Out.
   - **Unique Referral Link & QR Kit:** `https://nowing.net/?ref={referral_code}` with 1-click clipboard copy, custom sub-ID builder (`?sub=youtube`), and downloadable Mint Green banners.
   - **Real-Time Commission Ledger Table:** Date, Transaction ID, Masked Referred User (`u***@domain.com`), Purchase Amount ($), 15% Commission Earned ($ / VND), Status (`SETTLED`, `PENDING`, `REFUNDED`).
   - **Payout Settings & Request Engine:**
     - VietQR Bank Details: Bank Name (Napas 24/7 dropdown), Account Number, Account Holder Name.
     - Conversion to Platform Credits: Option to redeem balance for Nowing credits with a +10% bonus.
     - Payout Request Modal: Minimum threshold 500,000 VND ($20). Upon submission, locks requested balance and creates `PartnerPayout` record (`PENDING`).

6. **Given** a referred user completing a Stripe credit purchase (or VietQR top-up), **When** `_fulfill_completed_credit_purchase` in `app/routes/stripe_routes.py` processes the webhook, **Then**:
   - The backend checks if `purchase.user_id` has an active `PartnerReferral`.
   - If found, it calculates `commission_micros = int(purchase.amount_total_in_micros * partner.commission_rate)` (15%).
   - Atomically inserts a `PartnerCommission` record and updates `affiliate_partners.balance_micros += commission_micros` and `total_earned_micros += commission_micros`.

7. **Given** database schema requirements, **When** Alembic migration `215_add_affiliate_partner_tables.py` runs, **Then** it creates tables `affiliate_partners`, `partner_referrals`, `partner_commissions`, and `partner_payouts` with all foreign keys, UUID primary keys, and performance indexes.

## Tasks / Subtasks

- [x] Task 1: Database Schema & Migration (AC: 2, 4, 7)
  - [x] 1.1 Thêm các bảng `affiliate_partners`, `partner_referrals`, `partner_commissions`, `partner_payouts` trong `nowing_backend/app/db.py` với UUID primary keys, quan hệ SQLAlchemy, và indexes phù hợp.
  - [x] 1.2 Tạo file Alembic migration `nowing_backend/alembic/versions/215_add_affiliate_partner_tables.py` tạo cấu trúc bảng, enum `payout_status`, foreign keys và unique constraint trên `(partner_id, referred_user_id)`.
  - [x] 1.3 Tạo Pydantic schemas trong `nowing_backend/app/schemas/partner.py` (`PartnerProfileResponse`, `PartnerApplyRequest`, `PartnerCommissionItem`, `PartnerPayoutRequest`, `VietQrBankItem`, v.v.).
- [x] Task 2: Backend API Routes & Commission Lifecycle (AC: 2, 4, 6, 7)
  - [x] 2.1 Tạo service `nowing_backend/app/services/partner_service.py` xử lý nghiệp vụ: Đăng ký partner, tính 15% hoa hồng từ `CreditPurchase`, cập nhật số dư nguyên tử (`SELECT FOR UPDATE`), quy đổi USD sang VND (tỷ giá 25,400), tạo lệnh rút VietQR Napas 24/7 và chuyển đổi credit wallet (+10% bonus).
  - [x] 2.2 Tạo router `nowing_backend/app/routes/partner_routes.py` với các endpoint:
    - `POST /api/partners/apply`: Đăng ký tài khoản đối tác & cấp mã giới thiệu.
    - `GET /api/partners/me`: Xem hồ sơ, số dư USD/VND, tổng hoa hồng tích lũy và link giới thiệu.
    - `PUT /api/partners/payout-settings`: Cập nhật tài khoản ngân hàng thụ hưởng.
    - `GET /api/partners/referrals`: Danh sách khách hàng đã giới thiệu (email ẩn danh).
    - `GET /api/partners/commissions`: Sổ cái hoa hồng 15% trọn đời.
    - `POST /api/partners/payouts/request`: Yêu cầu thanh toán hoa hồng (VietQR / Credit).
    - `GET /api/partners/payouts`: Lịch sử các đợt rút tiền.
  - [x] 2.3 Cập nhật `UserManager.on_after_register` trong `nowing_backend/app/users.py` để đọc cookie `nowing_ref` từ request và ghi nhận `PartnerReferral`.
  - [x] 2.4 Cập nhật `_fulfill_completed_credit_purchase` trong `nowing_backend/app/routes/stripe_routes.py` để tự động tính 15% hoa hồng và ghi nhận vào sổ cái `PartnerCommission`.
  - [x] 2.5 Đăng ký `partner_routes` trong `nowing_backend/app/routes/__init__.py`.
- [x] Task 3: Redesign & Modernize `/pricing` Page (AC: 1)
  - [x] 3.1 Nâng cấp `nowing_web/components/pricing/pricing-section.tsx` và `nowing_web/app/(home)/pricing/page.tsx` sang Origami Mint Green Design:
    - Card $0 Free (Open-Core / Free Cloud Starter) với badge "Community & Open-Core".
    - Card Pay As You Go với badge "Phổ biến nhất" & bảng đơn giá minh bạch (Mở khóa SĐT, Deep Research, Crawlers, LLMs).
    - Card Enterprise với CTA Contact Sales.
  - [x] 3.2 Xây dựng `PricingLeadCalculator.tsx` (Slider số lượng Lead / Scrapes / Báo cáo $\rightarrow$ Tự động tính chi phí USD & VND).
  - [x] 3.3 Thêm Feature Comparison Matrix và bảng đơn giá theo đơn vị minh bạch.
  - [x] 3.4 Cập nhật SEO JSON-LD (`SoftwareApplication`, `Offer`, `FAQPage`).
- [x] Task 4: Public `/partners` Landing Page & Cookie Attribution (AC: 2, 3)
  - [x] 4.1 Xây dựng `nowing_web/app/(home)/partners/page.tsx` với giao diện Origami sang trọng: Hero 15% hoa hồng trọn đời, Value Props cho Agency/Freelancer, Testimonials, FAQ.
  - [x] 4.2 Xây dựng `PartnerEarningsCalculator.tsx` tính toán thu nhập thụ động theo số lượng khách hàng giới thiệu.
  - [x] 4.3 Xây dựng client hook `useReferralTracker.ts` và gắn vào `nowing_web/app/(home)/layout.tsx` để bắt query param `?ref=CODE` và lưu vào cookie `nowing_ref` (30 ngày).
- [x] Task 5: Authenticated Partner Portal / Dashboard (AC: 5)
  - [x] 5.1 Xây dựng `nowing_web/app/(home)/partners/dashboard/page.tsx`:
    - Header: Mã giới thiệu, Link chia sẻ (`nowing.net/?ref=CODE`), nút Copy 1-click, QR Code preview.
    - 4 Thẻ KPI: Tổng Click, Tổng Khách Hàng, Hoa Hồng Tích Lũy, Số Dư Khả Dụng.
    - Tab 1: **Sổ cái hoa hồng (Commission Ledger)** với thời gian thực, mã giao dịch, số tiền nạp, 15% hoa hồng nhận được.
    - Tab 2: **Danh sách khách hàng (Referrals List)**.
    - Tab 3: **Yêu cầu rút tiền (Payouts & VietQR)**: Form nhập STK ngân hàng (VietinBank, Vietcombank, Techcombank, MB, ACB...), Nút rút tiền nhanh, Lịch sử giải ngân.
  - [x] 5.2 Xây dựng API service `nowing_web/lib/apis/partners-api.service.ts` kết nối đầy đủ các endpoint backend.
- [x] Task 6: Testing & Quality Gates (AC: 1-7)
  - [x] 6.1 Backend unit & route tests:
    - `tests/unit/services/test_partner_service.py` (Áp dụng affiliate, tính 15% hoa hồng, chặn tự giới thiệu, rút tiền VietQR & credit bonus). (9/9 passed)
    - `tests/unit/routes/test_partner_routes.py` (FastAPI router endpoints tests). (4/4 passed)
  - [x] 6.2 Frontend typecheck & lint: `pnpm tsc --noEmit` & `pnpm exec biome check` (0 errors, 0 warnings).

## Dev Notes

- **Anti-Self Referral Guard:** Kiểm tra `user.id != partner.user_id` và chặn trường hợp tự nạp tiền lấy hoa hồng.
- **VietQR Napas Integration:** Sử dụng mã chuẩn ngân hàng Việt Nam (Vietcombank: `970436`, Techcombank: `970407`, MBBank: `970422`, ACB: `970416`, VPBank: `970432`...).
- **Atomic Balance Updates:** Thao tác cộng hoa hồng hoặc trừ số dư khi tạo yêu cầu rút tiền sử dụng `with_for_update()` trong transaction.
- **Zero Breaking Changes to Stripe Webhooks:** `_fulfill_completed_credit_purchase` bọc hook partner trong `try...except` để đảm bảo an toàn.

### Project Structure Notes

- **Backend New Files:**
  - `nowing_backend/app/schemas/partner.py`
  - `nowing_backend/app/services/partner_service.py`
  - `nowing_backend/app/routes/partner_routes.py`
  - `nowing_backend/alembic/versions/215_add_affiliate_partner_tables.py`
  - `nowing_backend/tests/unit/services/test_partner_service.py`
  - `nowing_backend/tests/unit/routes/test_partner_routes.py`
- **Backend Modified Files:**
  - `nowing_backend/app/db.py` (Thêm models `AffiliatePartner`, `PartnerReferral`, `PartnerCommission`, `PartnerPayout` và relationship trên `User`)
  - `nowing_backend/app/schemas/__init__.py` (Exports cho schemas)
  - `nowing_backend/app/users.py` (Hook `on_after_register` đọc cookie `nowing_ref`)
  - `nowing_backend/app/routes/stripe_routes.py` (Hook `_fulfill_completed_credit_purchase` tính 15% hoa hồng)
  - `nowing_backend/app/routes/__init__.py` (Include `partner_routes.router`)
- **Frontend New Files:**
  - `nowing_web/contracts/types/partners.types.ts`
  - `nowing_web/lib/apis/partners-api.service.ts`
  - `nowing_web/hooks/useReferralTracker.ts`
  - `nowing_web/components/pricing/PricingLeadCalculator.tsx`
  - `nowing_web/components/partners/PartnerEarningsCalculator.tsx`
  - `nowing_web/app/(home)/partners/page.tsx`
  - `nowing_web/app/(home)/partners/dashboard/page.tsx`
- **Frontend Modified Files:**
  - `nowing_web/components/pricing/pricing-section.tsx`
  - `nowing_web/app/(home)/pricing/page.tsx`
  - `nowing_web/app/(home)/layout.tsx`
  - `nowing_web/components/homepage/navbar.tsx`

### References

- [Epics & Stories: `_bmad-output/planning-artifacts/epics.md` (FR-88, Story 21.18, AD-42)]
- [Architecture Spine: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (AD-8, AD-10, AD-42)]
- [Stripe Wallet Architecture: `nowing_backend/app/routes/stripe_routes.py`]

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash (High) / Antigravity Agent

### Debug Log References

- Validated against BMAD Story Checklist (`checklist.md`): Zero omissions, anti-self-referral security guards, atomic database locking, Napas 24/7 VietQR integration, and 15% lifetime recurring commission ledger.

### Completion Notes List

- Task 1: Alembic migration 215, SQLAlchemy models (`AffiliatePartner`, `PartnerReferral`, `PartnerCommission`, `PartnerPayout`), and Pydantic schemas complete.
- Task 2: `PartnerService`, `partner_routes`, `UserManager.on_after_register` cookie extraction, `_fulfill_completed_credit_purchase` 15% commission hook complete.
- Task 3: Modernized `/pricing` page with Origami Mint Green design, $0 Free Open-core tier, transparent unit rates table, interactive `PricingLeadCalculator`, and partner CTA banner.
- Task 4: Public `/partners` landing page with value props, `PartnerEarningsCalculator`, 30-day cookie tracker (`useReferralTracker`), and Napas 24/7 supported bank showcase.
- Task 5: Authenticated `/partners/dashboard` portal with referral link/QR generator, KPI summary cards, realtime commissions ledger, referrals list, and VietQR payout request modal.
- Task 6: 13/13 backend pytest unit tests passing, ruff lint clean, `pnpm tsc --noEmit` passing with 0 errors, `biome check` passing with 0 errors.

### File List

- `nowing_backend/alembic/versions/215_add_affiliate_partner_tables.py`
- `nowing_backend/app/db.py`
- `nowing_backend/app/schemas/partner.py`
- `nowing_backend/app/schemas/__init__.py`
- `nowing_backend/app/services/partner_service.py`
- `nowing_backend/app/routes/partner_routes.py`
- `nowing_backend/app/routes/__init__.py`
- `nowing_backend/app/users.py`
- `nowing_backend/app/routes/stripe_routes.py`
- `nowing_backend/tests/unit/services/test_partner_service.py`
- `nowing_backend/tests/unit/routes/test_partner_routes.py`
- `nowing_web/contracts/types/partners.types.ts`
- `nowing_web/lib/apis/partners-api.service.ts`
- `nowing_web/hooks/useReferralTracker.ts`
- `nowing_web/components/pricing/PricingLeadCalculator.tsx`
- `nowing_web/components/pricing/pricing-section.tsx`
- `nowing_web/components/partners/PartnerEarningsCalculator.tsx`
- `nowing_web/app/(home)/partners/page.tsx`
- `nowing_web/app/(home)/partners/dashboard/page.tsx`
- `nowing_web/app/(home)/layout.tsx`
- `nowing_web/components/homepage/navbar.tsx`
- `_bmad-output/implementation-artifacts/stories/21-18-partners-affiliate-portal-and-0-pricing-page-deployment.md`
- `_bmad-output/implementation-artifacts/21-18-partners-affiliate-portal-and-0-pricing-page-deployment.md`
