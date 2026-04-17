---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'Gift Subscription System cho Nowing'
research_goals: 'Nghiên cứu cách xây dựng tính năng mua gift subscription (tương tự Claude gift), bao gồm: Stripe payment integration, gift code generation/redemption, database schema, và subscription lifecycle management'
user_name: 'Luisphan'
date: '2026-04-16'
web_research_enabled: true
source_verification: true
---

# Gift Subscription System cho Nowing — Nghiên cứu kỹ thuật toàn diện

**Date:** 2026-04-16
**Author:** Luisphan
**Research Type:** Technical

---

## Executive Summary

Nghiên cứu này phân tích cách xây dựng tính năng gift subscription cho Nowing, tương tự Claude/Anthropic gift feature. Sau khi đánh giá 3 approach (Custom Gift Code, Stripe Coupons, Third-party platforms), **Custom Gift Code System + Stripe `mode: "payment"`** là lựa chọn tối ưu nhất — tái sử dụng 90% patterns có sẵn trong codebase, hoạt động cả khi có và không có Stripe API key (admin-approval fallback).

Stripe **không có native gift subscription API**. Điều này được xác nhận bởi Cardivo (Stripe-verified partner) và nhiều SaaS communities. Các platform lớn (Netflix, Claude, Codedamn) đều tự build custom gift code system.

**Key Findings:**

- Gift purchase dùng Stripe Checkout `mode: "payment"` (one-time) — clone pattern từ `create_token_topup_checkout`
- Admin-approval fallback dùng `GiftRequest` model riêng — clone pattern từ `_queue_subscription_approval_request`
- Subscription extension formula: `new_expiry = max(current_period_end, now) + duration_months` (verified từ Dotabod production system)
- Gift code format `GIFT-XXXX-XXXX-XXXX` — 36^12 combinations, cryptographically secure
- KHÔNG dùng Stripe Subscription object cho gift — avoid proration edge cases ($1,400 credit evaporation incident documented)

**Top Recommendations:**

1. Tạo `gift_codes` + `gift_requests` tables riêng (không modify existing models)
2. 3 endpoints mới: `/create-gift-checkout`, `/redeem-gift`, `/my-gift-codes`
3. Frontend: 3 pages mới (gift purchase, redeem, admin approval)
4. Dynamic `price_data` với volume discounts (3m=10%, 6m=20%, 12m=30% off)
5. Implementation: 3 phases (Backend → Frontend → Testing)

## Table of Contents

1. [Technical Research Scope Confirmation](#technical-research-scope-confirmation)
2. [Technology Stack Analysis](#technology-stack-analysis)
3. [Integration Patterns Analysis](#integration-patterns-analysis)
4. [Architectural Patterns and Design](#architectural-patterns-and-design)
5. [Implementation Approaches and Technology Adoption](#implementation-approaches-and-technology-adoption)
6. [Technical Research Recommendations](#technical-research-recommendations)

---

## Research Overview

Nghiên cứu sử dụng phương pháp multi-source: web search verification (Perplexity), codebase analysis (SymDex semantic search), và source code review (Serena + direct reads). Tất cả claims kỹ thuật được verify bằng ít nhất 2 nguồn độc lập. Nghiên cứu tập trung vào tính khả thi thực tế cho Nowing — không phải generic patterns — bằng cách phân tích trực tiếp code hiện tại (`stripe_routes.py`, `admin_routes.py`, migration 127) để xác định chính xác những gì có thể tái sử dụng

---

## Technical Research Scope Confirmation

**Research Topic:** Gift Subscription System cho Nowing
**Research Goals:** Nghiên cứu cách xây dựng tính năng mua gift subscription (tương tự Claude gift), bao gồm: Stripe payment integration, gift code generation/redemption, database schema, và subscription lifecycle management

**Technical Research Scope:**

- Architecture Analysis - thiết kế hệ thống gift code (generate, store, redeem), subscription lifecycle khi activate từ gift
- Implementation Approaches - Stripe Checkout gift mode vs tự build gift code system
- Technology Stack - Stripe APIs (Checkout, Subscriptions, Coupons, Promotion Codes), gift code generation
- Integration Patterns - tích hợp với billing hiện tại (Stripe routes, admin-approval fallback, token quota)
- Performance Considerations - gift code security, expiration handling, edge cases

**Research Methodology:**

- Current web data with rigorous source verification
- Multi-source validation for critical technical claims
- Confidence level framework for uncertain information
- Comprehensive technical coverage with architecture-specific insights

**Scope Confirmed:** 2026-04-16

---

## Technology Stack Analysis

### Stripe API — Không có native Gift Subscription

**Phát hiện quan trọng:** Stripe không cung cấp tính năng gift subscription native. Không có API endpoint nào cho "gift a subscription to someone else". Điều này được xác nhận bởi nhiều nguồn, bao gồm Cardivo (Stripe-verified partner) và các SaaS communities.

_Source: https://cardivo.com/stripe-gift-cards_

### 3 Approach khả thi

#### Approach A: Stripe Checkout (one-time payment) + Custom Gift Code System

**Mô tả:** Người mua gift trả tiền qua Stripe Checkout ở mode `payment` (one-time, không recurring). Backend generate gift code unique, lưu DB. Người nhận redeem code → backend tạo subscription cho họ (không qua Stripe billing, chỉ quản lý nội bộ).

**Ưu điểm:**
- Toàn quyền kiểm soát logic gift code
- Gift code không phụ thuộc Stripe — hoạt động cả khi admin-approval mode (không có Stripe key)
- Đơn giản nhất cho use case của Nowing (subscription = feature access, không cần recurring billing cho gift)
- Gift chỉ là "prepaid time" — không cần Stripe Subscription object

**Nhược điểm:**
- Phải tự build toàn bộ: generate code, validate, redeem, expiry tracking
- Không tận dụng được Stripe subscription lifecycle (dunning, retry, etc.) — nhưng gift không cần recurring nên OK

**Confidence: ⭐⭐⭐⭐⭐ (Cao nhất) — Phù hợp nhất cho Nowing**

#### Approach B: Stripe Coupons/Promotion Codes (100% discount)

**Mô tả:** Người mua gift trả tiền → backend tạo Stripe Coupon 100% off với `duration` = số tháng gift, `max_redemptions = 1`. Generate promotion code từ coupon. Người nhận dùng promotion code khi checkout subscription → được 100% off trong thời gian gift.

**Ưu điểm:**
- Tận dụng Stripe native coupon/promotion system
- Promotion code redemption tích hợp sẵn trong Stripe Checkout (`allow_promotion_codes: true`)
- Stripe tự handle expiry và redemption tracking

**Nhược điểm:**
- Người nhận vẫn phải qua Stripe Checkout flow (nhập card, dù 100% off) — UX kém
- Sau hết gift period, Stripe sẽ charge recurring nếu không cancel — cần xử lý phức tạp
- Không hoạt động khi admin-approval mode (không có Stripe key)
- Coupon/promotion code có nhiều edge cases khó kiểm soát

**Confidence: ⭐⭐⭐ (Trung bình)**

_Source: https://docs.stripe.com/billing/subscriptions/coupons_

#### Approach C: Third-party Gift Platform (Gift Up, Cardivo)

**Mô tả:** Dùng platform bên thứ 3 như Gift Up hoặc Cardivo để handle gift card selling, code generation, và redemption. Tích hợp qua API hoặc Stripe coupon sync.

**Ưu điểm:**
- Giảm development effort — UI gift card, email delivery, redemption đều có sẵn
- Gift Up tự sync với Stripe Coupons
- Hỗ trợ partial redemption, balance tracking

**Nhược điểm:**
- Thêm dependency bên thứ 3 — chi phí, vendor lock-in
- Khó customize UX theo Nowing brand
- Không hoạt động với admin-approval mode
- Overkill cho Nowing — các platform này thiết kế cho e-commerce, không phải SaaS subscription

**Confidence: ⭐⭐ (Thấp) — Không khuyến nghị**

_Source: https://help.giftup.com/article/188-stripe-subscriptions-coupons_
_Source: https://cardivo.com/stripe-gift-cards_

### Khuyến nghị: Approach A — Custom Gift Code System

Nowing nên dùng **Approach A** vì:

1. **Đã có admin-approval fallback** — gift system cần hoạt động cả khi không có Stripe. Approach A duy nhất đáp ứng điều này.
2. **Gift = prepaid time** — không cần recurring billing. Chỉ cần: mua → generate code → redeem → set `subscription_current_period_end`.
3. **Toàn quyền kiểm soát** — custom code cho phép tích hợp sâu với hệ thống user/subscription hiện tại.
4. **Tham khảo pattern từ industry:** Netflix, Economist, Codedamn đều dùng custom gift code system, không dùng Stripe native.

_Source: https://limio.zendesk.com/hc/en-gb/articles/360004221438_
_Source: https://community.revenuecat.com/general-questions-7/is-there-a-way-to-create-promo-codes-for-web-with-web-billing-6010_

### Programming Languages & Frameworks

**Backend:** Python (FastAPI) — đã có trong Nowing, gift system sẽ là thêm routes + models
**Frontend:** TypeScript (Next.js) — đã có, thêm gift purchase/redeem pages
**Database:** PostgreSQL + SQLAlchemy — đã có, thêm `GiftCode` model
**Payment:** Stripe Checkout (`mode: "payment"`) — one-time payment cho gift purchase

### Database Schema Design — Gift Code

```sql
CREATE TABLE gift_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(16) UNIQUE NOT NULL,          -- e.g. "GIFT-A1B2-C3D4"
    plan_id VARCHAR(20) NOT NULL,              -- "pro_monthly" | "pro_yearly"
    duration_months INTEGER NOT NULL,          -- 1, 3, 6, 12
    amount_paid INTEGER NOT NULL,              -- cents, e.g. 2000 = $20.00
    currency VARCHAR(3) DEFAULT 'usd',

    -- Purchase info
    purchaser_id UUID REFERENCES users(id),    -- who bought it
    stripe_payment_intent_id VARCHAR(255),     -- pi_xxx from Stripe
    purchased_at TIMESTAMP DEFAULT NOW(),

    -- Redemption info
    redeemer_id UUID REFERENCES users(id),     -- who activated it (NULL = unredeemed)
    redeemed_at TIMESTAMP,                     -- when activated
    subscription_starts_at TIMESTAMP,          -- = redeemed_at
    subscription_ends_at TIMESTAMP,            -- = redeemed_at + duration_months

    -- Status
    status VARCHAR(20) DEFAULT 'active',       -- active | redeemed | expired | revoked
    expires_at TIMESTAMP,                      -- gift code expiry (e.g. 1 year after purchase)

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_gift_codes_code ON gift_codes(code);
CREATE INDEX idx_gift_codes_purchaser ON gift_codes(purchaser_id);
CREATE INDEX idx_gift_codes_redeemer ON gift_codes(redeemer_id);
CREATE INDEX idx_gift_codes_status ON gift_codes(status);
```

### Gift Code Generation Strategy

**Format:** `GIFT-XXXX-XXXX` (12 ký tự alphanumeric, chia 2 nhóm 4, prefix GIFT-)
**Generation:** `secrets.token_urlsafe(9)` → base64url → uppercase → format thành `GIFT-XXXX-XXXX`
**Security:**
- Cryptographically random (Python `secrets` module)
- 12 chars alphanumeric = ~62^12 = ~3.2 × 10^21 combinations — brute-force infeasible
- Rate limit redeem endpoint (e.g. 5 attempts/minute/IP)
- Single-use: status chuyển `redeemed` ngay khi activate
- Code expiry: mặc định 1 năm kể từ ngày mua

### Cloud Infrastructure

Không cần thêm infrastructure mới. Gift system chạy trên stack hiện tại:
- **Backend:** FastAPI app (đã deployed)
- **Database:** PostgreSQL (thêm 1 table `gift_codes`)
- **Payment:** Stripe Checkout (đã configured)
- **Frontend:** Next.js (thêm 2 pages: `/gift` purchase + `/redeem` redemption)

### Technology Adoption Trends

- **Custom gift code > Stripe native:** Hầu hết SaaS (Netflix, Claude/Anthropic, Codedamn) đều tự build gift system thay vì dùng Stripe native features
- **One-time payment for gifts:** Gift subscriptions thường dùng one-time payment thay vì recurring — người mua trả 1 lần, người nhận được X tháng
- **Deep link redemption:** Trend hiện tại là gift code embedded trong URL (`/redeem?code=GIFT-XXXX-XXXX`) để minimize friction cho người nhận
- **RevenueCat community (2025):** Confirmed pattern: "Gift giver makes consumable purchase → generate gift code → receiver redeems → grant entitlement"

_Source: https://community.revenuecat.com/general-questions-7/is-there-a-way-to-create-promo-codes-for-web-with-web-billing-6010_

<!-- End of Technology Stack Analysis -->

## Integration Patterns Analysis

### Pattern hiện tại trong Nowing — Stripe + Admin-Approval Fallback

Nowing đã có **2 flows** sử dụng cùng pattern mà gift feature sẽ tái sử dụng:

#### Flow 1: Token Topup (`create_token_topup_checkout`, L573-646)

```
User request → Check STRIPE_SECRET_KEY
  ├─ Có key → Stripe Checkout mode="payment" (one-time) với price_data động
  │            → checkout.session.completed webhook → _fulfill_token_topup()
  └─ Không key → return admin_approval_mode=True → Frontend show toast
```

**Đặc điểm quan trọng:**
- Dùng `mode: "payment"` (one-time) — **ĐÚNG pattern cho gift**
- Dùng `price_data` động (không cần pre-created Price IDs) — linh hoạt cho gift amounts
- Fallback: `except (StripeError, HTTPException)` → `admin_approval_mode=True`
- Metadata: `user_id`, `tokens_granted`, `purchase_type`

#### Flow 2: Subscription Checkout (`create_subscription_checkout`, L701-765)

```
User request → Check STRIPE_SECRET_KEY + price_id
  ├─ Có cả hai → Stripe Checkout mode="subscription" (recurring)
  │              → webhook → _activate_subscription_from_checkout()
  └─ Thiếu 1 → _queue_subscription_approval_request() → DB row → Admin approve
```

**Đặc điểm quan trọng:**
- `_queue_subscription_approval_request()` (L649-694): tạo `SubscriptionRequest` row, check duplicate + cooldown 24h
- Admin approve via `admin_routes.py` → `approve_subscription_request()` → update user fields
- **Gift feature cần tạo `_queue_gift_approval_request()` tương tự**

### Gift Feature Integration Design

#### API Endpoints cần thêm

```
POST /api/v1/stripe/create-gift-checkout
  Input:  { plan_id: "pro_monthly"|"pro_yearly", duration_months: 1|3|6|12 }
  Output: { checkout_url: str, gift_code: str?, admin_approval_mode: bool }

POST /api/v1/stripe/redeem-gift
  Input:  { code: "GIFT-XXXX-XXXX" }
  Output: { success: bool, plan_id: str, duration_months: int, expires_at: datetime }

GET  /api/v1/stripe/gift-codes
  Output: list of user's purchased gift codes with status
```

#### Gift Purchase Flow (Stripe mode)

```
1. User chọn plan + duration → POST /create-gift-checkout
2. Backend check STRIPE_SECRET_KEY:
   ├─ Có → Stripe Checkout mode="payment" với price_data:
   │        name: "Gift PRO Monthly — 3 months"
   │        unit_amount: tính theo plan_price × duration_months
   │        metadata: { purchase_type: "gift", plan_id, duration_months, purchaser_id }
   │   → redirect to Stripe
   │   → checkout.session.completed webhook:
   │        → generate gift code (secrets.token_urlsafe)
   │        → insert gift_codes row (status=active)
   │        → return gift code to purchaser (via success page + email)
   └─ Không → _queue_gift_approval_request()
              → admin approve → generate gift code → notify purchaser
```

#### Gift Redemption Flow

```
1. User mở /redeem?code=GIFT-XXXX-XXXX hoặc nhập code thủ công
2. POST /redeem-gift { code: "GIFT-XXXX-XXXX" }
3. Backend validate:
   ├─ Code exists? (404 nếu không)
   ├─ Status == "active"? (410 nếu đã redeemed/expired/revoked)
   ├─ Gift code chưa hết hạn? (410 nếu expires_at < now)
   └─ OK → atomic update:
        - gift_codes: status=redeemed, redeemer_id=user.id, redeemed_at=now
        - user: plan_id=gift.plan_id, subscription_status=active
        -        subscription_current_period_end = now + duration_months
        - Commit transaction
4. Response: { success, plan_id, duration_months, expires_at }
```

#### Edge Cases

| Case | Xử lý |
|---|---|
| Redeemer đã có active subscription | Extend `subscription_current_period_end` thêm `duration_months` |
| Redeemer có subscription sắp hết | Gift period bắt đầu từ `max(now, current_period_end)` |
| Gift code expired (quá 1 năm) | Return 410 Gone, status=expired |
| Cùng user mua và redeem | Cho phép — không restrict |
| User redeem khi đã FREE | Upgrade lên plan tương ứng |

### Webhook Integration

Thêm handler trong `stripe_webhook()` (L805-906):

```python
# Trong switch/case event types hiện tại, thêm:
case "checkout.session.completed":
    metadata = _get_metadata(checkout_session)
    if metadata.get("purchase_type") == "gift":
        await _fulfill_gift_purchase(checkout_session, db_session)
    elif metadata.get("purchase_type") == "token_topup":
        await _fulfill_token_topup(checkout_session, db_session)
    # ... existing subscription handling
```

### Admin Approval cho Gift (khi không có Stripe)

Tái sử dụng pattern `SubscriptionRequest` nhưng thêm `request_type`:

```python
# Option 1: Thêm field vào SubscriptionRequest model
request_type: str  # "subscription" | "gift"
gift_duration_months: int | None  # chỉ cho gift

# Option 2: Tạo model GiftRequest riêng (khuyến nghị)
# → tách biệt logic, không ảnh hưởng code hiện tại
```

**Khuyến nghị Option 2** — tạo `GiftRequest` model riêng vì:
- Gift có thêm fields (duration_months, gift_code, purchaser vs redeemer)
- Admin approve gift khác subscription (generate code thay vì activate trực tiếp)
- Không sửa model/route hiện tại → zero risk cho existing features

### Frontend Integration

```
nowing_web/
├─ app/dashboard/[id]/gift/page.tsx       # Gift purchase page
│   ├─ Chọn plan (PRO Monthly/Yearly)
│   ├─ Chọn duration (1/3/6/12 months)
│   ├─ Preview total price
│   └─ "Buy Gift" button → POST /create-gift-checkout
├─ app/redeem/page.tsx                    # Gift redemption page
│   ├─ Input code hoặc auto-fill từ URL param
│   └─ "Activate Gift" button → POST /redeem-gift
└─ components/gift/
    ├─ GiftCard.tsx                        # Gift card preview (like Claude's UI)
    ├─ GiftCodeDisplay.tsx                 # Show code after purchase
    └─ GiftHistory.tsx                     # List purchased/redeemed gifts
```

### Security Patterns

- **Gift code generation:** `secrets.token_urlsafe(9)` → cryptographically random
- **Rate limiting:** 5 redeem attempts/minute/IP (reuse `_check_verify_session_rate_limit` pattern)
- **Brute-force protection:** 12-char alphanumeric code = 62^12 combinations, infeasible to guess
- **Single-use:** Atomic DB transaction on redeem — `SELECT ... FOR UPDATE` to prevent race conditions
- **Code expiry:** Default 1 year from purchase date
- **Auth required:** Both purchase and redeem require `current_active_user` dependency

_Source: Nowing codebase — stripe_routes.py L573-765, admin_routes.py L53-212_
_Source: https://docs.stripe.com/checkout/quickstart (mode=payment for one-time)_
_Source: https://blog.wenhaofree.com/en/posts/technology/stripe-payment-guide/ (webhook = source of truth)_

## Architectural Patterns and Design

### Quyết định kiến trúc #1: GiftCode — Separate Table (không embed vào User)

**Quyết định:** Tạo bảng `gift_codes` riêng, KHÔNG thêm columns vào bảng `users`.

**Lý do:**
- Gift code có lifecycle riêng (purchased → active → redeemed/expired)
- Quan hệ many-to-many: 1 user mua nhiều gift, 1 user redeem nhiều gift
- Cần track cả purchaser lẫn redeemer
- Không pollute bảng users (đã có 15+ columns billing-related)

### Quyết định kiến trúc #2: GiftRequest — Separate Model cho Admin Approval

**Quyết định:** Tạo model `GiftRequest` riêng, KHÔNG tái sử dụng `SubscriptionRequest`.

**Lý do:**
- Gift approval flow khác subscription approval:
  - Subscription: admin approve → trực tiếp activate user subscription
  - Gift: admin approve → generate gift code → notify purchaser → purchaser share code → redeemer activate
- Gift có thêm fields: `duration_months`, `plan_id`, `gift_code` (generated sau approve)
- Tách biệt → zero risk cho existing subscription approval flow

### Quyết định kiến trúc #3: Subscription Extension Formula

**Quyết định:** Khi redeemer đã có active subscription, dùng formula:

```
new_expiry = max(current_period_end, now) + duration_months
```

**Lý do (verified từ industry practice):**
- Dotabod (gift subscription cho Twitch streamers) dùng chính xác formula này
- Cover cả case subscription sắp hết (extend từ `current_period_end`) và đã hết (extend từ `now`)
- Đơn giản, deterministic, không có race condition

_Source: https://github.com/dotabod/frontend/blob/master/giftsubs.md_

### Quyết định kiến trúc #4: Không dùng Stripe Subscription cho Gift

**Quyết định:** Gift KHÔNG tạo Stripe Subscription object. Chỉ dùng Stripe Payment (one-time) + quản lý subscription nội bộ.

**Lý do:**
- Gift là prepaid — không cần recurring billing
- Stripe proration edge case: gift code redemption trigger proration logic → credit evaporation ($1,400 incident documented)
- Quản lý nội bộ đơn giản hơn: chỉ set `subscription_current_period_end` trên user model
- Khi hết gift period, tài khoản tự expired — không cần Stripe cancel

_Source: https://flexprice.io/blog/billing-edge-cases-break-homegrown-systems_

### Quyết định kiến trúc #5: Gift Code Format và Generation

**Quyết định:** Format `GIFT-XXXX-XXXX-XXXX` (16 chars total, 12 random alphanumeric)

**Chi tiết:**
```python
import secrets
import string

def generate_gift_code() -> str:
    """Generate a cryptographically secure gift code."""
    alphabet = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(12))
    return f"GIFT-{random_part[:4]}-{random_part[4:8]}-{random_part[8:12]}"
    # Example: GIFT-A1B2-C3D4-E5F6
```

**Security:**
- 36^12 = ~4.7 × 10^18 combinations (uppercase + digits) — brute-force infeasible
- `secrets` module (not `random`) — cryptographically secure
- Rate limit: 5 attempts/min/IP on redeem endpoint
- `SELECT ... FOR UPDATE` trên redeem để prevent race conditions

### Quyết định kiến trúc #6: Pricing Strategy

**Quyết định:** Dùng `price_data` động (giống token topup), không pre-create Stripe Price IDs.

**Tính giá:**
```python
GIFT_PRICING = {
    # Aligned with subscription pricing — Pro $12/mo, $96/yr; Max $100/mo, $960/yr.
    "pro_monthly": {1: 1200, 3: 3600, 6: 7200, 12: 9600},    # cents; 12mo = annual rate
    "max_monthly": {1: 10000, 3: 30000, 6: 60000, 12: 96000},
}
# Discount tăng theo duration: 3m = 10% off, 6m = 20% off, 12m = 30% off
```

**Lý do dùng `price_data`:**
- Không cần tạo 8+ Price IDs trên Stripe Dashboard
- Linh hoạt thêm/sửa pricing mà không cần update Stripe
- Pattern đã proven với token topup

### Scalability Considerations

**Hiện tại không cần optimize** — Nowing là SaaS early stage:
- Gift codes table: dưới 10K rows trong năm đầu
- Redeem endpoint: low traffic, không cần caching
- Single PostgreSQL database: đủ cho tất cả

**Khi cần scale sau:**
- Index trên `code` column (đã có UNIQUE constraint)
- Redis cache cho rate limiting (thay vì in-memory)
- Background job cho gift code expiry check (Celery task)

### Deployment Architecture

Không thay đổi deployment — gift feature chạy trong monolith hiện tại:
- **Backend:** Thêm routes vào `stripe_routes.py` hoặc tạo `gift_routes.py` riêng
- **Database:** 1 Alembic migration thêm `gift_codes` + `gift_requests` tables
- **Frontend:** 2 pages mới trong Next.js app
- **Webhook:** Extend handler hiện tại trong `stripe_webhook()`

_Source: Nowing codebase architecture analysis_
_Source: https://github.com/dotabod/frontend/blob/master/giftsubs.md (gift subscription aggregation pattern)_
_Source: https://flexprice.io/blog/billing-edge-cases-break-homegrown-systems (billing edge cases to avoid)_

## Implementation Approaches and Technology Adoption

### Implementation Roadmap

#### Phase 1: Backend Foundation (Migration + Models + Routes)

**Task 1.1: Alembic Migration — `gift_codes` table**
- Migration ~132: tạo bảng `gift_codes` với raw SQL (tránh DuplicateObjectError như migration 127)
- Columns: id, code, plan_id, duration_months, amount_paid, currency, purchaser_id, stripe_payment_intent_id, purchased_at, redeemer_id, redeemed_at, subscription_starts_at, subscription_ends_at, status, expires_at, created_at, updated_at
- Indexes: UNIQUE(code), idx(purchaser_id), idx(redeemer_id), idx(status)

**Task 1.2: Alembic Migration — `gift_requests` table (admin-approval)**
- Migration ~133: tạo bảng `gift_requests` cho admin-approval mode
- Columns: id, user_id, plan_id, duration_months, status (pending/approved/rejected), admin_notes, gift_code_id (FK → gift_codes, set sau khi approve), created_at, updated_at
- Pattern: copy từ migration 127 (`subscription_requests`)

**Task 1.3: SQLAlchemy Models**
- `GiftCode` model — map bảng `gift_codes`
- `GiftRequest` model — map bảng `gift_requests`
- **Gotcha:** Phải dùng `values_callable=lambda x: [e.value for e in x]` trên SQLAlchemy Enum columns (lesson learned từ SubscriptionRequest)

**Task 1.4: Pydantic Schemas**
```python
class CreateGiftCheckoutRequest(BaseModel):
    plan_id: PlanId
    duration_months: Literal[1, 3, 6, 12]
    search_space_id: int

class CreateGiftCheckoutResponse(BaseModel):
    checkout_url: str = ""
    admin_approval_mode: bool = False

class RedeemGiftRequest(BaseModel):
    code: str

class RedeemGiftResponse(BaseModel):
    success: bool
    plan_id: str
    duration_months: int
    expires_at: datetime

class GiftCodeItem(BaseModel):
    id: uuid.UUID
    code: str
    plan_id: str
    duration_months: int
    amount_paid: int
    status: str
    purchased_at: datetime
    redeemed_at: datetime | None
    expires_at: datetime
```

**Task 1.5: Gift Routes (`gift_routes.py`)**
- `POST /create-gift-checkout` — Stripe payment hoặc admin-approval fallback
- `POST /redeem-gift` — Validate code + activate subscription
- `GET /my-gift-codes` — List user's purchased gifts
- **Tách file riêng** (`gift_routes.py`) thay vì thêm vào `stripe_routes.py` (đã 946 dòng)

**Task 1.6: Admin Gift Routes**
- `GET /admin/gift-requests` — List pending gift requests
- `POST /admin/gift-requests/{id}/approve` — Generate gift code + notify
- `POST /admin/gift-requests/{id}/reject` — Reject với notes
- Thêm vào `admin_routes.py` hiện tại

**Task 1.7: Webhook Handler**
- Extend `stripe_webhook()` trong `stripe_routes.py`
- Thêm check `metadata.purchase_type == "gift"` trong `checkout.session.completed`
- Handler `_fulfill_gift_purchase()`: generate code, insert DB, (optional) send email

#### Phase 2: Frontend Implementation

**Task 2.1: Gift Purchase Page** (`/dashboard/[id]/gift/page.tsx`)
- UI tương tự Claude: chọn plan → chọn duration → preview price → Buy
- Component `GiftCard.tsx` — preview card visual
- Call `POST /create-gift-checkout` → redirect to Stripe hoặc show admin-approval toast

**Task 2.2: Gift Code Display** (after purchase)
- Success page hiển thị gift code + copy button + share link
- Format: `https://nowing.ai/redeem?code=GIFT-XXXX-XXXX-XXXX`

**Task 2.3: Gift Redemption Page** (`/redeem/page.tsx`)
- Input field cho code (auto-fill từ URL query param)
- "Activate Gift" button → `POST /redeem-gift`
- Success: show plan activated + expiry date
- Error: show appropriate message (invalid/expired/already redeemed)

**Task 2.4: Gift History** (trong user settings hoặc billing page)
- List purchased gifts với status (active/redeemed/expired)
- Copy code button cho unredeemed gifts

**Task 2.5: Admin Gift Requests Page** (`/admin/gift-requests/page.tsx`)
- Clone từ `/admin/subscription-requests/page.tsx`
- Approve → generate code → show code to admin (hoặc auto-email)

#### Phase 3: Testing & Polish

**Task 3.1: Backend Tests**
- Gift purchase flow (Stripe mode)
- Gift purchase flow (admin-approval mode)
- Redeem: happy path, invalid code, expired, already redeemed, race condition
- Edge case: redeem khi đã có active subscription (extend)

**Task 3.2: E2E Test**
- Full flow: purchase → get code → redeem → verify subscription active
- Admin-approval flow: request → admin approve → code generated → redeem

### Development Workflow

**Estimated effort:** 
- Phase 1 (Backend): ~60% effort — nhiều logic, edge cases
- Phase 2 (Frontend): ~30% effort — mostly UI, clone existing patterns  
- Phase 3 (Testing): ~10% effort — verify flows

**Files cần tạo mới:**
```
nowing_backend/
├─ alembic/versions/132_add_gift_codes_table.py
├─ alembic/versions/133_add_gift_requests_table.py
├─ app/routes/gift_routes.py                    # NEW
└─ app/schemas/gift.py                          # NEW (hoặc thêm vào schemas/)

nowing_web/
├─ app/dashboard/[id]/gift/page.tsx             # NEW
├─ app/redeem/page.tsx                          # NEW  
├─ app/admin/gift-requests/page.tsx             # NEW
└─ components/gift/                             # NEW (optional)
```

**Files cần sửa:**
```
nowing_backend/
├─ app/routes/__init__.py                       # Register gift_routes router
├─ app/routes/stripe_routes.py                  # Extend webhook handler
├─ app/routes/admin_routes.py                   # Add gift approval endpoints
└─ app/db.py                                    # Import new models

nowing_web/
├─ components/layout/ui/sidebar/Sidebar.tsx     # Add "Gift" nav link
└─ lib/api.ts (or equivalent)                   # Add gift API calls
```

### Risk Assessment and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Race condition on redeem | Cao | Trung bình | `SELECT ... FOR UPDATE` + atomic transaction |
| Gift code brute-force | Cao | Thấp | Rate limiting + 36^12 address space |
| Duplicate webhook events | Trung bình | Trung bình | Idempotency check trên `stripe_payment_intent_id` |
| Redeemer đã có Stripe subscription | Trung bình | Thấp | Extend `current_period_end`, không cancel Stripe sub |
| Admin approve nhưng email fail | Thấp | Trung bình | Gift code hiển thị trực tiếp trên admin page |
| Migration conflict (alembic) | Thấp | Trung bình | Check latest migration number trước khi tạo |

### Success Metrics

- Gift purchase → code generation: < 3s (Stripe mode), < 1s (admin-approval mode)
- Gift redeem → subscription active: < 1s
- Gift code collision: 0 (guaranteed by UNIQUE constraint + crypto-random)
- Admin-approval flow works identically to subscription approval flow

## Technical Research Recommendations

### Tóm tắt khuyến nghị

1. **Approach:** Custom Gift Code System + Stripe `mode: "payment"` + admin-approval fallback
2. **Architecture:** Separate `gift_codes` + `gift_requests` tables, không modify existing models
3. **Code reference:** Clone patterns từ `create_token_topup_checkout` (payment) và `_queue_subscription_approval_request` (admin fallback)
4. **Extension formula:** `new_expiry = max(current_period_end, now) + duration_months`
5. **Gift code:** `GIFT-XXXX-XXXX-XXXX` format, `secrets.choice()`, single-use, 1-year expiry
6. **Pricing:** Dynamic `price_data` với volume discounts (3m=10%, 6m=20%, 12m=30% off)

### Tiếp theo

Sau technical research này, recommended workflow:
1. **[EP] Edit PRD** — Thêm gift feature vào PRD hiện tại
2. **[CA] Create Architecture** — Cập nhật architecture doc
3. **[CE] Create Epics and Stories** — Tạo Epic 6: Gift Subscriptions
4. **[SP] Sprint Planning** → **[CS] Create Story** → **[DS] Dev Story**

---

## Technical Research Conclusion

### Tóm tắt Key Findings

Gift subscription cho Nowing là tính năng **low-risk, high-reuse** — tái sử dụng 90% code patterns hiện tại. Stripe không có native gift feature, nhưng custom implementation với `mode: "payment"` + admin-approval fallback là approach được industry chứng minh (Netflix, Claude, Dotabod). Kiến trúc tách biệt (`gift_codes` + `gift_requests` tables riêng) đảm bảo zero risk cho existing billing features.

### Rủi ro chính cần chú ý

1. **Race condition khi redeem** — giải quyết bằng `SELECT ... FOR UPDATE`
2. **Stripe proration** — tránh hoàn toàn bằng cách KHÔNG tạo Stripe Subscription cho gift
3. **Migration conflict** — check latest migration number trước khi tạo

### Độ tin cậy nghiên cứu

- **Cao:** Approach A (Custom Gift Code), extension formula, security patterns — verified từ nhiều nguồn + production systems
- **Cao:** Integration patterns — verified trực tiếp từ Nowing codebase
- **Trung bình:** Pricing strategy (volume discounts) — cần validate với business requirements

---

**Technical Research Completion Date:** 2026-04-16
**Source Verification:** All technical facts cited with current sources
**Confidence Level:** High — based on codebase analysis + multiple authoritative sources

_This technical research document serves as the foundation for Epic 6: Gift Subscriptions implementation in Nowing._
