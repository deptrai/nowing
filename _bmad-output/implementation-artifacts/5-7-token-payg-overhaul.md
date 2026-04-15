# Story 5.7: Token PAYG Overhaul — Chuyển từ mua trang ETL sang mua token LLM

Status: done

## Story

As a User,
I want to mua thêm LLM token khi hết quota hàng tháng (pay-as-you-go),
so that tôi không cần nâng plan vẫn dùng được, hoặc khi cần dùng thêm với chi phí thấp hơn subscription.

## Acceptance Criteria

1. PAYG "Buy Pages" cũ bị xóa hoàn toàn — không còn endpoint/UI mua trang ETL.
2. User có thể mua token packs (100K/$1, 500K/$4, 1M/$7) qua Stripe one-time checkout.
3. Token đã mua (`purchased_tokens`) được cộng vào quota hiện tại: `monthly_token_limit + purchased_tokens`.
4. `purchased_tokens` bị reset về 0 khi billing cycle renews (hết token hoặc hết period — tùy điều kiện nào đến trước).
5. Sidebar hiển thị: plan badge (FREE/PRO), token meter bao gồm purchased, "Buy More Tokens" CTA, "Upgrade to Pro" (free users) / "Manage Billing" (pro users).
6. Settings có tab "Subscription" hiển thị plan info, usage meters, billing portal link.
7. Stripe Customer Portal endpoint cho user tự quản lý subscription (cancel, update card).

## Changes Made

### Backend

| File | Thay đổi |
|---|---|
| `surfsense_backend/app/db.py` | Thêm `purchased_tokens` column vào cả 2 User model variants |
| `surfsense_backend/alembic/versions/130_add_purchased_tokens.py` | **NEW** migration — `purchased_tokens` INTEGER NOT NULL DEFAULT 0 |
| `surfsense_backend/app/config/__init__.py` | Thêm `TOKEN_PACKS` dict (3 packs với price_id env vars), `STRIPE_BILLING_PORTAL_RETURN_URL`; xóa `STRIPE_PAGE_BUYING_ENABLED`, `STRIPE_PAGES_PER_UNIT` |
| `surfsense_backend/app/schemas/stripe.py` | Xóa PAYG page schemas (`CreateCheckoutSessionRequest/Response`, `PagePurchaseRead`, `PagePurchaseHistoryResponse`); thêm `TokenPackId`, `CreateTokenTopupRequest/Response`, `BillingPortalResponse`; đổi `StripeStatusResponse.page_buying_enabled` → `stripe_enabled` |
| `surfsense_backend/app/routes/stripe_routes.py` | Xóa `create-checkout-session`, `purchases` endpoints + helper functions (`_ensure_page_buying_enabled`, `_get_required_stripe_price_id`, `_get_or_create_purchase_from_checkout_session`, `_mark_purchase_failed`, `_fulfill_completed_purchase`); thêm `create-token-topup-checkout`, `billing-portal` endpoints + `_fulfill_token_topup`; webhook `checkout.session.completed (payment mode)` gọi `_fulfill_token_topup`; `_handle_invoice_payment_succeeded` reset `purchased_tokens = 0` |
| `surfsense_backend/app/services/token_quota_service.py` | `token_limit = monthly_token_limit + purchased_tokens` |

### Frontend

| File | Thay đổi |
|---|---|
| `surfsense_web/contracts/types/stripe.types.ts` | Xóa PAYG page types; thêm `TokenPackId`, `CreateTokenTopupRequest/Response`, `BillingPortalResponse`; `stripe_enabled` thay `page_buying_enabled` |
| `surfsense_web/contracts/types/user.types.ts` | Thêm `purchased_tokens`, `subscription_current_period_end` |
| `surfsense_web/lib/apis/stripe-api.service.ts` | Xóa `createCheckoutSession`, `getPurchases`; thêm `createTokenTopupCheckout`, `getBillingPortal` |
| `surfsense_web/app/dashboard/[search_space_id]/buy-tokens/page.tsx` | **NEW** — Token pack selector UI (3 cards, balance display) |
| `surfsense_web/app/dashboard/[search_space_id]/purchase-success/page.tsx` | Repurpose: "Tokens added!" thay "Purchase complete" |
| `surfsense_web/components/layout/ui/sidebar/PageUsageDisplay.tsx` | Plan badge, token meter = monthly + purchased, CTAs: Buy Tokens / Upgrade / Manage Billing |
| `surfsense_web/components/layout/providers/LayoutDataProvider.tsx` | Pass `purchasedTokens`, `planId`, `subscriptionStatus` xuống sidebar |
| `surfsense_web/components/settings/subscription-content.tsx` | **NEW** — Settings tab: plan info, usage, billing portal |
| `surfsense_web/components/settings/user-settings-dialog.tsx` | Tab "Purchase History" → "Subscription" |
| `surfsense_web/components/settings/more-pages-content.tsx` | "Buy page packs" → "Upgrade to Pro" + "Buy Token Top-up" |

### Files Deleted

| File | Lý do |
|---|---|
| `surfsense_web/app/dashboard/[search_space_id]/buy-pages/page.tsx` | PAYG pages route thay bằng buy-tokens |
| `surfsense_web/components/settings/buy-pages-content.tsx` | PAYG pages UI |
| `surfsense_web/app/dashboard/[search_space_id]/user-settings/components/PurchaseHistoryContent.tsx` | PAYG history thay bằng SubscriptionContent |

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
| `STRIPE_TOKEN_PACK_100K_PRICE_ID` | Stripe Price ID cho 100K token pack |
| `STRIPE_TOKEN_PACK_500K_PRICE_ID` | Stripe Price ID cho 500K token pack |
| `STRIPE_TOKEN_PACK_1M_PRICE_ID` | Stripe Price ID cho 1M token pack |
| `STRIPE_BILLING_PORTAL_RETURN_URL` | URL trả về sau khi user rời billing portal |

## Dev Notes

- `PagePurchase` model/table giữ nguyên trong DB cho data cũ — không drop table, chỉ không tạo row mới
- Webhook handler dùng `metadata.token_pack` + `metadata.purchase_type = "token_packs"` để phân biệt token topup vs subscription
- `_fulfill_token_topup` dùng `SELECT ... FOR UPDATE` trên User row để tránh race condition khi Stripe retry webhook
- Token purchased expires ở end of billing period (whichever comes first: hết token hoặc hết period)

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
| `surfsense_backend/app/schemas/stripe.py` | Thêm `max_monthly`, `max_yearly` vào `PlanId` enum |
| `surfsense_backend/app/config/__init__.py` | Thêm `STRIPE_MAX_MONTHLY_PRICE_ID`, `STRIPE_MAX_YEARLY_PRICE_ID` env vars; PLAN_LIMITS: `max_monthly/max_yearly` = 20M tokens, 20K pages |
| `surfsense_backend/app/routes/stripe_routes.py` | `_get_price_id_for_plan()` xử lý max plans; webhook validation chấp nhận `max_monthly`/`max_yearly`; `_activate_subscription_from_checkout()` map max plans → PLAN_LIMITS |
| `surfsense_backend/alembic/versions/131_add_dexscreener_connector.py` | **NEW** — Resolve Alembic multiple-head conflict (down_revision=130) |

### Frontend Changes (MAX Plan)

| File | Thay đổi |
|---|---|
| `surfsense_web/components/pricing/pricing-section.tsx` | Thêm MAX plan card ($100/mo, $80/mo annual, 20M tokens); `handleUpgradeMax()` function; `PLAN_IDS.max_monthly/max_yearly` |
| `surfsense_web/components/pricing.tsx` | Fix grid layout 4 plans: `lg:grid-cols-4` khi `plans.length === 4` |
| `surfsense_web/components/settings/more-pages-content.tsx` | Title → "Get Free Tokens & Pages"; thêm "Claim 100K Free Tokens" card; token claim dialog via mailto |

---

## Token Consumption Display Per Message

Hiển thị token tiêu thụ sau mỗi AI response và quota còn lại trong chat UI.

### Backend Changes

| File | Thay đổi |
|---|---|
| `surfsense_backend/app/tasks/chat/stream_new_chat.py` | Sau `update_token_usage()`, emit SSE event `data-token-usage` với `tokens_this_request`, `tokens_used_total`, `monthly_limit`, `tokens_remaining`; cả 2 paths (new message + resume); resume path: di chuyển token deduction trước `format_done()` để SSE còn mở |

### Frontend Changes

| File | Thay đổi |
|---|---|
| `surfsense_web/lib/chat/streaming-state.ts` | Thêm `data-token-usage` vào `SSEEvent` union type |
| `surfsense_web/app/dashboard/[search_space_id]/new-chat/[[...chat_id]]/page.tsx` | `lastTokenUsage` state; reset khi send message mới; `case "data-token-usage"` trong cả 3 switch blocks; overlay UI phía trên composer hiển thị stats sau khi stream hoàn tất |

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
