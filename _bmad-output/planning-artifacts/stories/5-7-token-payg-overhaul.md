# Story 5.7: Token PAYG Overhaul — Chuyển từ mua trang ETL sang mua token LLM

Status: done

## Story

As a User,
I want to mua thêm LLM token khi hết quota hàng tháng (pay-as-you-go),
so that tôi không cần nâng plan vẫn dùng được, hoặc khi cần dùng thêm với chi phí thấp hơn subscription.

## Acceptance Criteria

1. PAYG "Buy Pages" cũ bị xóa hoàn toàn — không còn endpoint/UI mua trang ETL.
2. User có thể mua token top-up với **custom amount** (bất kỳ số tiền USD > 0). Rate: **$1 USD = 100,000 tokens** (`_TOKENS_PER_USD = 100_000`). Dùng Stripe `price_data` — **không cần pre-created Stripe Price IDs**.
3. Token đã mua (`purchased_tokens`) được cộng vào quota hiện tại: `monthly_token_limit + purchased_tokens`.
4. `purchased_tokens` bị reset về 0 khi billing cycle renews (hết token hoặc hết period — tùy điều kiện nào đến trước).
5. Sidebar hiển thị: plan badge (FREE/PRO/PRO YEARLY/PRO MONTHLY), token meter bao gồm purchased, "Buy More Tokens" CTA, "Upgrade to Pro" (free users) / "Manage Billing" (pro users).
6. Settings có tab "Subscription" hiển thị plan info, usage meters, billing portal link.
7. Stripe Customer Portal endpoint cho user tự quản lý subscription (cancel, update card).
8. **Admin-approval fallback**: Khi Stripe không configured (không có `STRIPE_SECRET_KEY`) hoặc Stripe API call fails (placeholder/invalid credentials), cả subscription checkout lẫn token topup đều fallback sang admin-approval mode — trả `admin_approval_mode=true`, frontend hiện toast hướng dẫn liên hệ admin.

## Changes Made

### Backend

| File | Thay đổi |
|---|---|
| `nowing_backend/app/db.py` | Thêm `purchased_tokens` column vào cả 2 User model variants |
| `nowing_backend/alembic/versions/130_add_purchased_tokens.py` | **NEW** migration — `purchased_tokens` INTEGER NOT NULL DEFAULT 0 |
| `nowing_backend/app/config/__init__.py` | Thêm `STRIPE_BILLING_PORTAL_RETURN_URL`; xóa `STRIPE_PAGE_BUYING_ENABLED`, `STRIPE_PAGES_PER_UNIT`, `TOKEN_PACKS` dict (không cần nữa — dùng `price_data` thay vì pre-created Price IDs) |
| `nowing_backend/app/schemas/stripe.py` | Xóa PAYG page schemas; thêm `CreateTokenTopupRequest(amount_usd: float, search_space_id: int)`, `CreateTokenTopupResponse(checkout_url, admin_approval_mode)`, `BillingPortalResponse`; đổi `StripeStatusResponse.page_buying_enabled` → `stripe_enabled` |
| `nowing_backend/app/routes/stripe_routes.py` | Xóa `create-checkout-session`, `purchases` endpoints; thêm `create-token-topup-checkout` (custom USD amount, `price_data`), `billing-portal`, `_fulfill_token_topup`, `_resolve_plan_price_id()`, `_queue_subscription_approval_request()`; `_TOKENS_PER_USD = 100_000` constant; admin-approval fallback cho cả token topup và subscription checkout khi Stripe fails; webhook `checkout.session.completed (payment mode)` gọi `_fulfill_token_topup`; `_handle_invoice_payment_succeeded` reset `purchased_tokens = 0` |
| `nowing_backend/app/services/token_quota_service.py` | `token_limit = monthly_token_limit + purchased_tokens` |

### Frontend

| File | Thay đổi |
|---|---|
| `nowing_web/contracts/types/stripe.types.ts` | Xóa PAYG page types; thêm `createTokenTopupRequest(amount_usd, search_space_id)`, `createTokenTopupResponse(checkout_url, admin_approval_mode)`, `BillingPortalResponse`; `stripe_enabled` thay `page_buying_enabled` |
| `nowing_web/contracts/types/user.types.ts` | Thêm `purchased_tokens`, `subscription_current_period_end` |
| `nowing_web/lib/apis/stripe-api.service.ts` | Xóa `createCheckoutSession`, `getPurchases`; thêm `createTokenTopupCheckout`, `getBillingPortal` |
| `nowing_web/app/dashboard/[search_space_id]/buy-tokens/page.tsx` | **NEW** — Custom amount token topup UI: quick amount buttons ($1/$5/$10/$25/$50/$100), custom amount input with +/- controls, token preview badge, admin-approval toast handling |
| `nowing_web/app/dashboard/[search_space_id]/purchase-success/page.tsx` | Repurpose: "Tokens added!" thay "Purchase complete" |
| `nowing_web/components/layout/ui/sidebar/PageUsageDisplay.tsx` | Plan badge (FREE/PRO MONTHLY/PRO YEARLY), token meter = monthly + purchased, CTAs: Buy Tokens / Upgrade / Manage Billing; nhận `purchasedTokens`, `planId`, `subscriptionStatus` props |
| `nowing_web/components/layout/ui/sidebar/Sidebar.tsx` | Forward `purchasedTokens`, `planId`, `subscriptionStatus` từ `pageUsage` vào `PageUsageDisplay` |
| `nowing_web/components/layout/types/layout.types.ts` | `PageUsage` interface thêm `purchasedTokens?`, `planId?`, `subscriptionStatus?` |
| `nowing_web/components/layout/providers/LayoutDataProvider.tsx` | Pass `purchasedTokens`, `planId`, `subscriptionStatus` xuống sidebar |
| `nowing_web/atoms/user/user-query.atoms.ts` | `staleTime: 0` (từ 5 phút) — refetch on window focus |
| `nowing_backend/app/schemas/users.py` | `UserRead` thêm `purchased_tokens: int`, `subscription_current_period_end: datetime | None` |
| `nowing_web/components/settings/subscription-content.tsx` | **NEW** — Settings tab: plan info, usage, billing portal |
| `nowing_web/components/settings/user-settings-dialog.tsx` | Tab "Purchase History" → "Subscription" |
| `nowing_web/components/settings/more-pages-content.tsx` | "Buy page packs" → "Upgrade to Pro" + "Buy Token Top-up" |

### Files Deleted

| File | Lý do |
|---|---|
| `nowing_web/app/dashboard/[search_space_id]/buy-pages/page.tsx` | PAYG pages route thay bằng buy-tokens |
| `nowing_web/components/settings/buy-pages-content.tsx` | PAYG pages UI |
| `nowing_web/app/dashboard/[search_space_id]/user-settings/components/PurchaseHistoryContent.tsx` | PAYG history thay bằng SubscriptionContent |

## Token Quota Model

```
Effective Limit = monthly_token_limit (from plan) + purchased_tokens (from PAYG)
Available = Effective Limit - tokens_used_this_month
```

Reset khi billing cycle: `tokens_used_this_month = 0`, `purchased_tokens = 0`.

## API Endpoints

| Method | Path | Mô tả |
|---|---|---|
| POST | `/api/v1/stripe/create-token-topup-checkout` | Tạo Stripe checkout cho token pack |
| GET | `/api/v1/stripe/billing-portal` | Tạo Stripe Customer Portal session URL |
| GET | `/api/v1/stripe/status` | Trả `stripe_enabled` (thay `page_buying_enabled`) |
| POST | `/api/v1/stripe/create-subscription-checkout` | Giữ nguyên |
| GET | `/api/v1/stripe/verify-checkout-session` | Giữ nguyên |
| POST | `/api/v1/stripe/webhook` | Cập nhật: payment mode → token grant |

### Removed Endpoints

| Method | Path | Lý do |
|---|---|---|
| POST | `/api/v1/stripe/create-checkout-session` | PAYG pages |
| GET | `/api/v1/stripe/purchases` | PAYG purchase history |

## Environment Variables Mới

| Biến | Mô tả |
|---|---|
| `STRIPE_BILLING_PORTAL_RETURN_URL` | URL trả về sau khi user rời billing portal |

> **Note**: Không cần `STRIPE_TOKEN_PACK_*_PRICE_ID` env vars nữa — token topup dùng Stripe `price_data` (inline price tạo lúc checkout). Rate cố định `$1 = 100K tokens`.

## Dev Notes

- `PagePurchase` model/table giữ nguyên trong DB cho data cũ — không drop table, chỉ không tạo row mới
- Webhook handler dùng `metadata.purchase_type` = `"token_topup"` hoặc `"token_packs"` (cả 2 được accept) để phân biệt token topup vs subscription
- `_fulfill_token_topup` dùng `SELECT ... FOR UPDATE` trên User row để tránh race condition khi Stripe retry webhook; đọc `metadata.tokens_granted` để biết số token cần cộng
- Token purchased expires ở end of billing period (whichever comes first: hết token hoặc hết period)
- `_TOKENS_PER_USD = 100_000` — constant định nghĩa rate quy đổi USD → tokens
- **Admin-approval fallback**: `create_token_topup_checkout` và `create_subscription_checkout` đều catch `(StripeError, HTTPException)` và fallback sang admin-approval mode khi Stripe API fails (kể cả placeholder/invalid credentials). `_queue_subscription_approval_request()` là extracted helper tạo `SubscriptionRequest` row
- `_resolve_plan_price_id(plan_id) -> str | None` — helper lookup price ID, trả `None` nếu thiếu env var (triggers admin-approval)
- `UserRead` schema đã thêm `purchased_tokens` và `subscription_current_period_end` để frontend nhận đủ data
- `PageUsage` type và `Sidebar.tsx` đã thêm `purchasedTokens`, `planId`, `subscriptionStatus` props
- `currentUserAtom` `staleTime` giảm từ 5 phút xuống 0 — user data refetch mỗi khi window focus, đảm bảo sidebar cập nhật ngay sau admin approval hoặc topup

---

# Addendum (2026-04-16): MAX Plan + Token Consumption Display

## MAX Plan

Thêm gói MAX vào cả backend và frontend (bổ sung cho Story 5.7 sau billing overhaul).

### Pricing

| Plan | Monthly | Annual | Tokens/mo | Pages/mo |
|---|---|---|---|---|
| FREE | $0 | $0 | 50K | 500 |
| PRO | $12 | $8/mo ($96/yr) | 1M | 5K |
| MAX | $100 | $80/mo ($960/yr) | 20M | 20K |
| ENTERPRISE | Custom | Custom | Unlimited | Unlimited |

Token economics: MAX = $5/M tokens (58% cheaper per token vs PRO $12/M).

### Backend Changes (MAX Plan)

| File | Thay đổi |
|---|---|
| `nowing_backend/app/schemas/stripe.py` | Thêm `max_monthly`, `max_yearly` vào `PlanId` enum |
| `nowing_backend/app/config/__init__.py` | Thêm `STRIPE_MAX_MONTHLY_PRICE_ID`, `STRIPE_MAX_YEARLY_PRICE_ID` env vars; PLAN_LIMITS: `max_monthly/max_yearly` = 20M tokens, 20K pages |
| `nowing_backend/app/routes/stripe_routes.py` | `_get_price_id_for_plan()` xử lý max plans; webhook validation chấp nhận `max_monthly`/`max_yearly`; `_activate_subscription_from_checkout()` map max plans → PLAN_LIMITS |
| `nowing_backend/alembic/versions/131_add_dexscreener_connector.py` | **NEW** — Resolve Alembic multiple-head conflict (down_revision=130) |

### Frontend Changes (MAX Plan)

| File | Thay đổi |
|---|---|
| `nowing_web/components/pricing/pricing-section.tsx` | Thêm MAX plan card ($100/mo, $80/mo annual, 20M tokens); `handleUpgradeMax()` function; `PLAN_IDS.max_monthly/max_yearly` |
| `nowing_web/components/pricing.tsx` | Fix grid layout 4 plans: `lg:grid-cols-4` khi `plans.length === 4` |
| `nowing_web/components/settings/more-pages-content.tsx` | Title → "Get Free Tokens & Pages"; thêm "Claim 100K Free Tokens" card; token claim dialog via mailto |

---

## Token Consumption Display Per Message

Hiển thị token tiêu thụ sau mỗi AI response và quota còn lại trong chat UI.

### Backend Changes

| File | Thay đổi |
|---|---|
| `nowing_backend/app/tasks/chat/stream_new_chat.py` | Sau `update_token_usage()`, emit SSE event `data-token-usage` với `tokens_this_request`, `tokens_used_total`, `monthly_limit`, `tokens_remaining`; cả 2 paths (new message + resume); resume path: di chuyển token deduction trước `format_done()` để SSE còn mở |

### Frontend Changes

| File | Thay đổi |
|---|---|
| `nowing_web/lib/chat/streaming-state.ts` | Thêm `data-token-usage` vào `SSEEvent` union type |
| `nowing_web/app/dashboard/[search_space_id]/new-chat/[[...chat_id]]/page.tsx` | `lastTokenUsage` state; reset khi send message mới; `case "data-token-usage"` trong cả 3 switch blocks; overlay UI phía trên composer hiển thị stats sau khi stream hoàn tất |

### Token Usage Overlay UI

```
Request: X tokens  |  Used: Y / Z  |  Remaining: W
```

- Hiển thị khi `lastTokenUsage !== null && !isRunning`
- `Remaining` đỏ khi < 10% monthly limit còn lại
- Ẩn khi bắt đầu request mới

### SSE Event Schema

```json
{
  "type": "data-token-usage",
  "data": {
    "tokens_this_request": 1234,
    "tokens_used_total": 56789,
    "monthly_limit": 1000000,
    "tokens_remaining": 943211
  }
}
```

### New Environment Variables (MAX Plan)

| Biến | Mô tả |
|---|---|
| `STRIPE_MAX_MONTHLY_PRICE_ID` | Stripe Price ID cho MAX Monthly ($100/mo) |
| `STRIPE_MAX_YEARLY_PRICE_ID` | Stripe Price ID cho MAX Annual ($960/yr) |
