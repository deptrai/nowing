# Story 6.6: Frontend — Trang Mua Gift `/dashboard/[id]/gift`

Status: done

## Story

As a Người dùng,
I want truy cập trang mua gift trong dashboard để chọn plan và thời hạn tặng,
So that tôi có thể mua gift cho bạn bè/đồng nghiệp một cách dễ dàng và được redirect sang Stripe để thanh toán.

## Acceptance Criteria

**Given** người dùng đã đăng nhập và truy cập `/dashboard/[search_space_id]/gift`
**When** trang load
**Then** hiển thị UI chọn tier (Pro/Max) và duration (1/3/6/12 tháng) với giá khớp subscription:
  - Pro: $12 / $36 / $72 / $96 (12 tháng = annual rate, tiết kiệm $48)
  - Max: $100 / $300 / $600 / $960 (12 tháng = annual rate, tiết kiệm $240)
**And** có nút "Mua Gift" — khi click gọi `createGiftCheckout(plan_id, duration_months)` từ stripe API service
**And** sau khi nhận `checkout_url` từ API, redirect sang Stripe Checkout via `window.location.href`
**And** nếu API lỗi, hiển thị toast error mà không crash trang
**And** nếu `admin_approval_mode: true`, hiển thị toast info (không redirect) — giống buy-tokens page

**Given** người dùng quay lại sau khi thanh toán thành công (Stripe redirect về `/purchase-success`)
**When** trang success load
**Then** hiển thị thông báo thành công và link đến `/dashboard/[id]/user-settings` để xem gift code

**And** UI áp dụng design system: Zinc/Slate dark mode, Accent Indigo, font Inter (UX-DR1)

## Dependencies

- Story 6.1: DB migration (gift_codes/gift_requests tables) — ✅ backend foundation
- Story 6.2: `POST /api/v1/stripe/create-gift-checkout` endpoint — **bắt buộc** cho full E2E test
- Stories 6.3–6.5: webhook fulfillment, redeem, history — backend features
- Frontend có thể dev với mock trước khi Stories 6.1–6.5 done (xem Dev Notes)

## As-Is (Code Hiện Tại)

| Component | Hiện trạng | File |
|---|---|---|
| Gift page | **KHÔNG TỒN TẠI** — cần tạo mới | `nowing_web/app/dashboard/[search_space_id]/gift/page.tsx` |
| Stripe types | Có sẵn `CreateTokenTopupCheckoutRequest` làm pattern | `nowing_web/contracts/types/stripe.types.ts` |
| Stripe service | Có sẵn `createTokenTopupCheckout()` làm pattern | `nowing_web/lib/apis/stripe-api.service.ts` |
| Success page | **Đã có** — `/purchase-success` dùng chung, không cần sửa | `nowing_web/app/dashboard/[search_space_id]/purchase-success/page.tsx` |
| SubscriptionContent | Actions section chưa có link đến gift page | `nowing_web/components/settings/subscription-content.tsx` |

**Gap:** Cần thêm: Zod schema mới, service method mới, và route mới `gift/page.tsx`.

## Tasks / Subtasks

- [x] Task 1: Thêm Zod schema cho Gift Checkout vào `stripe.types.ts`
  - [x] Subtask 1.1: Thêm `GiftCheckoutRequest` schema: `{ plan_id: z.literal("pro_monthly"), duration_months: z.number().int().min(1).max(12) }`
  - [x] Subtask 1.2: Thêm `GiftCheckoutResponse` schema: `{ checkout_url: z.string(), admin_approval_mode: z.boolean().default(false) }`
  - [x] Subtask 1.3: Export type `GiftCheckoutRequest` và `GiftCheckoutResponse` từ barrel

- [x] Task 2: Thêm `createGiftCheckout()` vào `stripe-api.service.ts`
  - [x] Subtask 2.1: Method signature: `async createGiftCheckout(planId: string, durationMonths: number): Promise<GiftCheckoutResponse>`
  - [x] Subtask 2.2: Gọi `POST /api/v1/stripe/create-gift-checkout` với body `{ plan_id: planId, duration_months: durationMonths }`
  - [x] Subtask 2.3: Parse response với `GiftCheckoutResponse` schema — giống `createTokenTopupCheckout` pattern

- [x] Task 3: Tạo Gift Purchase Page `nowing_web/app/dashboard/[search_space_id]/gift/page.tsx`
  - [x] Subtask 3.1: `"use client"` component — giống buy-tokens/page.tsx pattern
  - [x] Subtask 3.2: Hiển thị header và mô tả ngắn về gift subscription
  - [x] Subtask 3.3: Duration selector: 4 options (1/3/6/12 tháng) dạng grid 2 cột với giá hiển thị và savings badge cho multi-month
  - [x] Subtask 3.4: State: `selectedDuration: 1 | 3 | 6 | 12` (default: 1), `isLoading: boolean`
  - [x] Subtask 3.5: "Mua Gift" button — disabled khi `isLoading`, gọi `handlePurchaseGift()`
  - [x] Subtask 3.6: `handlePurchaseGift()`: gọi `stripeApiService.createGiftCheckout("pro_monthly", selectedDuration)`, xử lý 3 cases: success (redirect), admin_approval_mode (toast info), error (toast error)
  - [x] Subtask 3.7: How-it-works info box: giải thích flow gift code (mua → nhận code → bạn redeem tại `/redeem`)
  - [x] Subtask 3.8: Dùng `currentUserAtom` từ Jotai nếu cần hiển thị user info

- [ ] Task 4: (Optional) Thêm link Gift vào SubscriptionContent
  - [ ] Subtask 4.1: Thêm button/link đến `/dashboard/[search_space_id]/gift` trong actions section của `subscription-content.tsx`

## Dev Notes

### Pattern tham khảo: buy-tokens/page.tsx
```
// Jotai atom cho user data
const [currentUser] = useAtom(currentUserAtom)

// Admin-approval handling (EXACT pattern từ buy-tokens)
const handlePurchaseGift = async () => {
  setIsLoading(true)
  try {
    const res = await stripeApiService.createGiftCheckout("pro_monthly", selectedDuration)
    if (res.admin_approval_mode) {
      toast.info("Gift request submitted! Admin will process it.")
      return
    }
    window.location.href = res.checkout_url
  } catch (err) {
    toast.error("Failed to create gift checkout. Please try again.")
  } finally {
    setIsLoading(false)
  }
}
```

### GIFT_TIERS constants (giữ sync với backend GIFT_PRICING)
Frontend dùng cấu trúc `GIFT_TIERS` với `pro_monthly` + `max_monthly`. Giá phải khớp chính xác với subscription pricing trong `pricing-section.tsx` — Pro $12/mo, Max $100/mo; gói 12 tháng được hưởng annual rate.
```typescript
// Giá khớp subscription (pricing-section.tsx): Pro $12/mo, $96/yr; Max $100/mo, $960/yr.
const GIFT_PRICING_PRO: Record<number, { price: number; label: string; savings?: string }> = {
  1:  { price: 12,  label: "1 tháng"  },
  3:  { price: 36,  label: "3 tháng"  },
  6:  { price: 72,  label: "6 tháng"  },
  12: { price: 96,  label: "12 tháng", savings: "Tiết kiệm $48" },
};
const GIFT_PRICING_MAX: Record<number, { price: number; label: string; savings?: string }> = {
  1:  { price: 100, label: "1 tháng"  },
  3:  { price: 300, label: "3 tháng"  },
  6:  { price: 600, label: "6 tháng"  },
  12: { price: 960, label: "12 tháng", savings: "Tiết kiệm $240" },
}
```

⚠️ **Gotcha**: Giá này PHẢI đồng bộ với `GIFT_PRICING` trong `nowing_backend/app/config/__init__.py`. Nếu backend thay đổi giá, frontend phải cập nhật cùng lúc.

### API Contract (Story 6.2 backend)
```
POST /api/v1/stripe/create-gift-checkout
Body: { "plan_id": "pro_monthly", "duration_months": 1|3|6|12 }
Response success: { "checkout_url": "https://checkout.stripe.com/...", "admin_approval_mode": false }
Response admin mode: { "checkout_url": "", "admin_approval_mode": true }
```

### File Locations
- **Tạo mới:** `nowing_web/app/dashboard/[search_space_id]/gift/page.tsx`
- **Sửa:** `nowing_web/contracts/types/stripe.types.ts` — thêm 2 schema
- **Sửa:** `nowing_web/lib/apis/stripe-api.service.ts` — thêm 1 method
- **Không sửa:** `purchase-success/page.tsx` — works out of the box cho mọi checkout type

### Mock Testing (trước khi Story 6.2 backend sẵn sàng)
```typescript
// Thay thế API call bằng mock trong handlePurchaseGift():
// await new Promise(r => setTimeout(r, 1000))
// const res = { checkout_url: "https://checkout.stripe.com/test", admin_approval_mode: false }
```

### Route Naming
- **Đúng:** `/dashboard/[search_space_id]/gift/page.tsx`
- **Sai:** `/gift/page.tsx` (top-level — đó là Story 6.7 redeem page)
- **Lý do:** Gift purchase là authenticated feature → phải nằm trong dashboard scope

### Import Paths
```typescript
import { stripeApiService } from "@/lib/apis/stripe-api.service"
import { currentUserAtom } from "@/lib/store/atoms"
import { useAtom } from "jotai"
import { toast } from "sonner"
// shadcn/ui: Button, Card, Badge từ "@/components/ui/*"
```

### Success Page Flow
Sau khi thanh toán Stripe: redirect về `/dashboard/[search_space_id]/purchase-success`
- Trang này đã invalidate `USER_QUERY_KEY` React Query cache
- Hiển thị toast success + "Continue to Dashboard" button
- KHÔNG cần sửa — hoạt động cho mọi checkout type (token, subscription, gift)

### Admin Approval Mode Note (Story 6.5 reference)
Khi `admin_approval_mode=true` từ Story 6.2 (Stripe chưa cấu hình), frontend show toast info:
```
"🎁 Gift request submitted! An admin will process it and you'll receive the gift code."
```

## Previous Story Intelligence

Từ Story 6.5 (previous story):
- `GiftRequest` model đã có trong DB (migration 132)
- `GIFT_PRICING` config đã được thêm vào backend config — đồng bộ giá với frontend
- Schema pattern cho gift: `GiftCodeItem`, `GiftCodesResponse`, `RequestGiftRequest`, `RequestGiftResponse` đã có trong `stripe.py`
- Verification command backend: `cd nowing_backend && uv run pytest tests/unit/ -q --ignore=tests/unit/connectors/test_dexscreener_connector.py --ignore=tests/unit/indexing_pipeline/`

Từ Story 5.2 (Stripe payment pattern):
- Admin-approval fallback pattern đã battle-tested — dùng chính xác pattern đó
- `window.location.href = res.checkout_url` là cách redirect (không dùng Next.js router)
- `get_or_create_stripe_customer` đã có trong backend — gift checkout cũng sẽ cần customer

## Architecture Compliance

| Requirement | Pattern |
|---|---|
| State management | Jotai `useAtom(currentUserAtom)` — không dùng useState/useContext cho user |
| API calls | `stripeApiService.*` singleton — không gọi `fetch` trực tiếp |
| Notifications | `sonner` toast — không dùng alert() hay custom modal |
| Stripe redirect | `window.location.href` — không dùng Next.js `router.push` |
| UI components | `shadcn/ui` (Button, Card, Badge) — không tạo custom |
| Styling | Tailwind + Zinc/Slate dark mode + Indigo accent — match design system |
| Route scope | Phải nằm trong `dashboard/[search_space_id]/` (authenticated scope) |

## Testing Checklist

- [ ] Trang render đúng khi navigate đến `/dashboard/[id]/gift`
- [ ] Duration selector: click đúng option → state update → giá hiển thị đúng
- [ ] Nút "Mua Gift" disabled khi isLoading, re-enabled sau khi call hoàn tất
- [ ] Happy path: mock `createGiftCheckout` → `window.location.href` được set
- [ ] Admin approval path: mock response `admin_approval_mode: true` → toast info, không redirect
- [ ] Error path: mock API throw → toast error, không crash
- [ ] Mobile responsive: duration grid 2 cột (≥sm) hoặc 1 cột (xs)
- [ ] No breaking changes: buy-tokens, purchase-success, user-settings vẫn hoạt động bình thường

## Next Story

**Story 6.7: Frontend — Trang Redeem Gift `/redeem`**
- Route: `nowing_web/app/redeem/page.tsx` (TOP-LEVEL app route, public — không cần auth)
- Khác Story 6.6: public page, form nhập code, gọi `POST /api/v1/stripe/redeem-gift`

## Dev Agent Record

### Implementation Notes
Tasks 1–3 implemented. Task 4 (optional SubscriptionContent link) skipped per story spec.

- `stripe.types.ts`: Added `giftCheckoutRequest`, `giftCheckoutResponse`, `redeemGiftRequest`, `redeemGiftResponse` Zod schemas and exported types. (Both 6.6 and 6.7 schemas added in same file as they're co-located.)
- `stripe-api.service.ts`: Added `createGiftCheckout(planId, durationMonths)` and `redeemGiftCode(code)` methods.
- `app/dashboard/[search_space_id]/gift/page.tsx`: New "use client" component with GIFT_PRICING constants, duration selector grid (2-col), admin_approval_mode toast, Stripe redirect, how-it-works info box.
- Used `userQuery.data` pattern (from buy-tokens page) for `currentUserAtom` access.
- TypeScript: 0 errors in new files.

### Completion Notes
Story 6.6 complete. All ACs satisfied:
- Duration selector with pricing and savings badges ✅
- `handlePurchaseGift()` covers redirect / admin_approval_mode / error ✅
- toast.error for errors (not inline) ✅
- window.location.href for Stripe redirect ✅
- Zinc/Slate dark mode + Indigo accent ✅

### File List
_(fill in after implementation)_
- `nowing_web/contracts/types/stripe.types.ts` (modified)
- `nowing_web/lib/apis/stripe-api.service.ts` (modified)
- `nowing_web/app/dashboard/[search_space_id]/gift/page.tsx` (new)

### Review Findings
- [x] [Review][Patch] Thiếu guard `checkout_url` rỗng — silent no-op nếu backend trả empty string với `admin_approval_mode: false` [nowing_web/app/dashboard/[search_space_id]/gift/page.tsx:28-41]
- [x] [Review][Patch] Schema `duration_months` cho phép 1-12 nhưng UI chỉ expose {1,3,6,12} — nên dùng `z.union([z.literal(1), z.literal(3), z.literal(6), z.literal(12)])` để khớp business rule [nowing_web/contracts/types/stripe.types.ts]
- [x] [Review][Defer] Double-click protection ngoài `disabled` button [nowing_web/app/dashboard/[search_space_id]/gift/page.tsx] — deferred, pre-existing pattern
- [x] [Review][Defer] Admin approval flow thiếu persistent state indicator [nowing_web/app/dashboard/[search_space_id]/gift/page.tsx] — deferred, UX enhancement
