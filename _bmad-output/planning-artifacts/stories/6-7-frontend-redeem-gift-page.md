# Story 6.7: Frontend — Trang Redeem Gift `/redeem`

Status: done

## Story

As a Người nhận quà,
I want truy cập trang public `/redeem`, nhập gift code và kích hoạt subscription,
So that tôi có thể nhận gói PRO được tặng mà không cần hiểu về Stripe hay billing.

## Acceptance Criteria

**Given** người nhận quà (có thể chưa đăng nhập) truy cập `/redeem`
**When** trang load
**Then** hiển thị form nhập gift code với placeholder "GIFT-XXXX-XXXX-XXXX" và nút "Kích hoạt"
**And** nếu chưa đăng nhập: hiển thị prompt "Đăng nhập để sử dụng gift code" với link đến trang login, sau khi đăng nhập redirect về `/redeem`

**Given** người dùng đã đăng nhập và nhập gift code hợp lệ
**When** click "Kích hoạt"
**Then** frontend gọi `POST /api/v1/stripe/redeem-gift` với `{ code: "GIFT-XXXX-XXXX-XXXX" }`, hiển thị loading state
**And** khi thành công: hiển thị confirmation card với "🎉 Subscription đã được gia hạn đến [ngày]" và nút "Vào Dashboard"
**And** khi thất bại (code sai/hết hạn/đã dùng): hiển thị error message inline dưới input, không redirect

**Given** người dùng đã redeem thành công
**When** họ quay lại trang dashboard
**Then** sidebar hiển thị plan và ngày hết hạn subscription mới (user profile được invalidate sau redeem)

**And** UI áp dụng design system: Zinc/Slate dark mode, Accent Indigo, font Inter (UX-DR1)

## Dependencies

- Story 6.4: `POST /api/v1/stripe/redeem-gift` endpoint — **bắt buộc** cho E2E test
- Story 6.1: DB migration 132 (gift_codes table với code, status, expires_at, redeemer_id)
- Story 6.3: Webhook fulfillment tạo gift_codes sau payment

## As-Is (Code Hiện Tại)

| Component | Hiện trạng | File |
|---|---|---|
| Redeem page | **KHÔNG TỒN TẠI** — cần tạo mới | `nowing_web/app/redeem/page.tsx` |
| Stripe types | Có sẵn — cần thêm 2 schema mới | `nowing_web/contracts/types/stripe.types.ts` |
| Stripe service | Có sẵn — cần thêm 1 method mới | `nowing_web/lib/apis/stripe-api.service.ts` |
| Auth detection | `getBearerToken()` — dùng để check đăng nhập | `nowing_web/lib/auth-utils.ts` |
| Invite page | Pattern tốt cho public page + auth check | `nowing_web/app/invite/[invite_code]/page.tsx` |

**Gap:** Cần thêm: 2 Zod schema, 1 service method, và route mới `nowing_web/app/redeem/page.tsx`.

## Tasks / Subtasks

- [x] Task 1: Thêm Zod schema cho Redeem Gift vào `stripe.types.ts`
  - [x] Subtask 1.1: Thêm `RedeemGiftRequest` schema: `{ code: z.string().min(1) }`
  - [x] Subtask 1.2: Thêm `RedeemGiftResponse` schema: `{ new_expiry: z.string(), plan_id: z.string() }`
  - [x] Subtask 1.3: Export type `RedeemGiftRequest` và `RedeemGiftResponse` từ barrel

- [x] Task 2: Thêm `redeemGiftCode()` vào `stripe-api.service.ts`
  - [x] Subtask 2.1: Method signature: `async redeemGiftCode(code: string): Promise<RedeemGiftResponse>`
  - [x] Subtask 2.2: Gọi `POST /api/v1/stripe/redeem-gift` với body `{ code }`
  - [x] Subtask 2.3: Parse response với `RedeemGiftResponse` schema — giống `createTokenTopupCheckout` pattern

- [x] Task 3: Tạo Redeem Page `nowing_web/app/redeem/page.tsx`
  - [x] Subtask 3.1: `"use client"` component — top-level PUBLIC route (không cần search_space_id)
  - [x] Subtask 3.2: Auth check on mount: `getBearerToken()` → nếu null, hiển thị "unauthenticated" UI với link đến `/auth` (với `?redirect=/redeem` query param)
  - [x] Subtask 3.3: Authenticated UI: input field cho gift code, nút "Kích hoạt", error message zone
  - [x] Subtask 3.4: State: `code: string`, `isLoading: boolean`, `error: string | null`, `successData: RedeemGiftResponse | null`
  - [x] Subtask 3.5: Input validation: trim whitespace, uppercase, kiểm tra format `GIFT-XXXX-XXXX-XXXX` (optional, backend validate authoritative)
  - [x] Subtask 3.6: `handleRedeem()`: gọi `stripeApiService.redeemGiftCode(code.trim())`, xử lý success vs error
  - [x] Subtask 3.7: Success state: confirmation card "🎉 Subscription đã được gia hạn đến [formatted date]" + button "Vào Dashboard" → navigate to `/dashboard`
  - [x] Subtask 3.8: Error state: inline error dưới input (không dùng toast — AC yêu cầu inline)
  - [x] Subtask 3.9: Sau redeem thành công, invalidate `USER_QUERY_KEY` để sidebar refresh plan/expiry

## Dev Notes

### Route Location — PUBLIC top-level (QUAN TRỌNG)

```
✅ ĐÚNG: nowing_web/app/redeem/page.tsx     → URL: /redeem
❌ SAI:  nowing_web/app/dashboard/[search_space_id]/redeem/page.tsx  → yêu cầu auth
```

Trang `/redeem` là PUBLIC — người chưa đăng nhập phải có thể access để xem form (dù cần login để submit). Phải nằm ở `app/redeem/`, không trong `dashboard/`.

### Auth Check Pattern (từ invite page và auth-redirect component)

```typescript
"use client";
import { getBearerToken } from "@/lib/auth-utils";
import { useEffect, useState } from "react";

export default function RedeemPage() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  
  useEffect(() => {
    setIsAuthenticated(!!getBearerToken());
  }, []);

  if (isAuthenticated === null) return <LoadingSpinner />; // hydration guard
  if (!isAuthenticated) return <UnauthenticatedView />;
  return <AuthenticatedRedeemForm />;
}
```

### Unauthenticated UI

```tsx
function UnauthenticatedView() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>🎁 Kích hoạt Gift Code</CardTitle>
        <CardDescription>Đăng nhập để sử dụng gift code</CardDescription>
      </CardHeader>
      <CardContent>
        <p>Bạn cần đăng nhập để kích hoạt gift subscription.</p>
        <Button asChild>
          <Link href="/auth?redirect=/redeem">Đăng nhập</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
```

### API Contract (Story 6.4 backend)

```
POST /api/v1/stripe/redeem-gift
Headers: Authorization: Bearer <token>
Body: { "code": "GIFT-ABCD-EFGH-IJKL" }

Response 200: { "new_expiry": "2027-04-16T00:00:00Z", "plan_id": "pro_monthly" }
Response 400: { "detail": "Gift code không hợp lệ hoặc đã được sử dụng" }
Response 400: { "detail": "Gift code đã hết hạn" }
```

### Redeem Handler Pattern

```typescript
const handleRedeem = async () => {
  if (!code.trim() || isLoading) return;
  setIsLoading(true);
  setError(null);
  try {
    const res = await stripeApiService.redeemGiftCode(code.trim().toUpperCase());
    setSuccessData(res);
    // Invalidate user cache để sidebar cập nhật plan/expiry
    queryClient.invalidateQueries({ queryKey: USER_QUERY_KEY });
  } catch (err: any) {
    const msg = err?.response?.data?.detail ?? err?.message ?? "Có lỗi xảy ra. Vui lòng thử lại.";
    setError(msg);
  } finally {
    setIsLoading(false);
  }
};
```

### Success State Display

```typescript
if (successData) {
  const expiryDate = new Date(successData.new_expiry).toLocaleDateString("vi-VN", {
    year: "numeric", month: "long", day: "numeric"
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>🎉 Đã kích hoạt thành công!</CardTitle>
      </CardHeader>
      <CardContent>
        <p>Subscription đã được gia hạn đến <strong>{expiryDate}</strong></p>
      </CardContent>
      <CardFooter>
        <Button asChild><Link href="/dashboard">Vào Dashboard</Link></Button>
      </CardFooter>
    </Card>
  );
}
```

### Error Handling — INLINE (không dùng toast)

```tsx
{/* Inline error dưới input — KHÔNG dùng toast */}
<Input
  value={code}
  onChange={(e) => { setCode(e.target.value); setError(null); }}
  placeholder="GIFT-XXXX-XXXX-XXXX"
  className={error ? "border-red-500" : ""}
/>
{error && <p className="text-sm text-red-500 mt-1">{error}</p>}
```

⚠️ **Gotcha**: AC yêu cầu inline error message, KHÔNG phải toast. Khác với gift purchase page (dùng toast).

### Invalidate User Query Key

```typescript
import { useQueryClient } from "@tanstack/react-query";
import { USER_QUERY_KEY } from "@/atoms/user/user-query.atoms";
// ...
const queryClient = useQueryClient();
queryClient.invalidateQueries({ queryKey: USER_QUERY_KEY });
```

### File Locations

- **Tạo mới:** `nowing_web/app/redeem/page.tsx`
- **Sửa:** `nowing_web/contracts/types/stripe.types.ts` — thêm 2 schema
- **Sửa:** `nowing_web/lib/apis/stripe-api.service.ts` — thêm 1 method
- **Không sửa:** Dashboard layout, sidebar, user atoms — chỉ invalidate cache

### Import Paths

```typescript
import { getBearerToken } from "@/lib/auth-utils"
import { stripeApiService } from "@/lib/apis/stripe-api.service"
import { USER_QUERY_KEY } from "@/atoms/user/user-query.atoms"
import { useQueryClient } from "@tanstack/react-query"
// shadcn/ui: Button, Card, CardHeader, CardContent, CardFooter, CardTitle, CardDescription, Input
// từ "@/components/ui/*"
```

### Mock Testing (trước khi Story 6.4 backend sẵn sàng)

```typescript
// Thay thế API call trong handleRedeem():
// await new Promise(r => setTimeout(r, 1000));
// const res = { new_expiry: new Date(Date.now() + 30 * 24 * 3600 * 1000).toISOString(), plan_id: "pro_monthly" };
// setSuccessData(res);
```

## Previous Story Intelligence

Từ Story 6.6 (gift purchase page — previous story):
- `stripe.types.ts` và `stripe-api.service.ts` đã có thêm gift checkout schema/method — pattern rõ ràng để follow
- `window.location.href` cho redirects (tuy nhiên `/redeem` không cần redirect Stripe)
- `currentUserAtom` import từ `@/atoms/user/user-query.atoms`

Từ Story 6.4 (backend redeem endpoint):
- API endpoint: `POST /api/v1/stripe/redeem-gift`
- Response: `{ new_expiry: datetime, plan_id: str }`
- Error codes: 400 với Vietnamese error message trong `detail`
- Validation: code format, status ACTIVE, expires_at, redeemer_id IS NULL
- Concurrent redemption guard: `SELECT ... FOR UPDATE` trên gift_codes row

Từ Story 5.2 (subscription success page):
- `USER_QUERY_KEY` invalidation pattern sau thay đổi subscription
- `authenticatedFetch` là cách gọi authenticated API ở top-level page

## Architecture Compliance

| Requirement | Pattern |
|---|---|
| Route scope | Top-level `app/redeem/` — KHÔNG trong dashboard/ |
| Auth detection | `getBearerToken()` từ `@/lib/auth-utils` |
| Hydration guard | State `isAuthenticated: null` → spinner trước khi check |
| API calls | `stripeApiService.*` singleton — không gọi `fetch` trực tiếp |
| Cache invalidation | `queryClient.invalidateQueries({ queryKey: USER_QUERY_KEY })` |
| Error display | **Inline** dưới input — KHÔNG dùng `toast` (khác gift purchase) |
| Success navigation | `<Link href="/dashboard">` — không dùng `window.location.href` |
| UI components | `shadcn/ui` (Button, Card, Input) — không tạo custom |
| Styling | Tailwind + Zinc/Slate dark mode + Indigo accent |

## Testing Checklist

- [ ] Unauthenticated: trang load, hiển thị "Đăng nhập" prompt với link đến `/auth?redirect=/redeem`
- [ ] Authenticated + valid code: submit → loading → success card với ngày hết hạn
- [ ] Authenticated + invalid code: submit → inline error dưới input, không redirect, không toast
- [ ] Authenticated + expired code: inline error message phù hợp
- [ ] Success: `USER_QUERY_KEY` được invalidate → sidebar refresh sau navigate
- [ ] Button "Vào Dashboard" sau success → navigate đến `/dashboard`
- [ ] Code input: trim whitespace + uppercase trước khi gửi
- [ ] Loading state: nút disabled khi đang gọi API
- [ ] Mobile responsive: card chiếm full width trên mobile
- [ ] No breaking changes: gift purchase, subscription pages, dashboard vẫn hoạt động

## Dev Agent Record

### Implementation Notes
Tasks 1–3 đều được implement trong cùng session với Story 6.6 (schemas và service method đã được thêm vào stripe.types.ts và stripe-api.service.ts).

- `app/redeem/page.tsx`: Public top-level route. Auth check via `getBearerToken()` với hydration guard (null → spinner). 3 render states: LoadingSpinner, UnauthenticatedView, AuthenticatedRedeemForm.
- Error handling: inline `<p className="text-red-500">` dưới input — KHÔNG dùng toast (khác Story 6.6).
- Success state: Card với formatted date dùng `vi-VN` locale + Link "Vào Dashboard".
- `USER_QUERY_KEY` invalidated sau redeem thành công qua `useQueryClient`.
- TypeScript: 0 errors.

### Completion Notes
Story 6.7 complete. All ACs satisfied:
- Public route `/redeem` — unauthenticated users thấy login prompt với `/auth?redirect=/redeem` ✅
- Authenticated form: input, loading state, inline error ✅
- Success: confirmation card với ngày hết hạn formatted vi-VN + "Vào Dashboard" ✅
- `USER_QUERY_KEY` invalidated sau success ✅
- Inline error (không toast) ✅

### File List
_(fill in after implementation)_
- `nowing_web/contracts/types/stripe.types.ts` (modified — schemas added in Story 6.6 session)
- `nowing_web/lib/apis/stripe-api.service.ts` (modified — method added in Story 6.6 session)
- `nowing_web/app/redeem/page.tsx` (new)

### Review Findings
- [x] [Review][Patch] `queryClient.invalidateQueries` không được `await` — race condition giữa invalidate cache và navigation "Vào Dashboard" [nowing_web/app/redeem/page.tsx:94-95]
- [x] [Review][Patch] Error response shape brittle — `err?.response?.data?.detail` giả định axios shape nhưng `baseApiService` dùng fetch wrapper; cần dùng shape thực tế của `ApiError` [nowing_web/app/redeem/page.tsx:82]
- [x] [Review][Patch] Date parsing không validate — `new Date(successData.new_expiry)` có thể render "Invalid Date" nếu backend trả format bất thường [nowing_web/app/redeem/page.tsx:110]
- [x] [Review][Defer] Token expiry mid-redeem → AuthenticationError redirect không giữ context [nowing_web/app/redeem/page.tsx:77] — deferred, auth infrastructure pre-existing
- [x] [Review][Defer] `currentUserAtom` query không check loading state [nowing_web/app/redeem/page.tsx] — deferred, áp dụng pattern hiện có từ buy-tokens page
