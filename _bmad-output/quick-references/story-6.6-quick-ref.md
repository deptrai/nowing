# Story 6.6 Quick Reference
## Gift Purchase Page Frontend Implementation

**Status:** Ready for Implementation  
**Effort:** 4-5 hours  
**Epic:** 6 (Gift Subscription)  

---

## TL;DR

Create `/dashboard/[search_space_id]/gift/page.tsx` that:
1. Shows 4 duration buttons (1, 3, 6, 12 months)
2. Displays prices: $20, $54, $96, $168
3. Shows savings badges for bundles
4. Calls `/api/v1/stripe/create-gift-checkout` on purchase
5. Redirects to Stripe Checkout URL
6. Follows `buy-tokens/page.tsx` pattern exactly

---

## Files to Modify

### 1. `nowing_web/contracts/types/stripe.types.ts`
**Add:**
```typescript
export const createGiftCheckoutRequest = z.object({
  plan_id: z.enum(["pro_monthly", "pro_yearly"]).default("pro_monthly"),
  duration_months: z.number().int().min(1).max(12),
});

export const createGiftCheckoutResponse = z.object({
  checkout_url: z.string(),
  admin_approval_mode: z.boolean().default(false),
});

export type CreateGiftCheckoutRequest = z.infer<typeof createGiftCheckoutRequest>;
export type CreateGiftCheckoutResponse = z.infer<typeof createGiftCheckoutResponse>;
```

### 2. `nowing_web/lib/apis/stripe-api.service.ts`
**Add method:**
```typescript
createGiftCheckout = async (
  request: CreateGiftCheckoutRequest
): Promise<CreateGiftCheckoutResponse> => {
  return baseApiService.post(
    "/api/v1/stripe/create-gift-checkout",
    createGiftCheckoutResponse,
    { body: request }
  );
};
```

### 3. **NEW FILE:** `nowing_web/app/dashboard/[search_space_id]/gift/page.tsx`
See full implementation in main guide.

---

## Key Constants

```typescript
const GIFT_PRICING = {
  1: 20,      // $20
  3: 54,      // $54 (save $6)
  6: 96,      // $96 (save $24)
  12: 168,    // $168 (save $72)
};

const DURATION_OPTIONS = [1, 3, 6, 12];
```

---

## Component Structure

```
Page (Client Component)
├── State
│   ├── selectedDuration
│   └── isLoading
├── Derived Data
│   ├── durationOptions (via useMemo)
│   └── selectedOption
├── Handler
│   └── handlePurchase() → stripeApiService.createGiftCheckout()
└── JSX
    ├── Header (h1 + description)
    ├── Duration Selection Card
    │   ├── 2x2 button grid
    │   ├── Summary box
    │   ├── Info box (explanation)
    │   └── Purchase button
    └── Footer (security note)
```

---

## API Contract

**Endpoint:** `POST /api/v1/stripe/create-gift-checkout`  
**Backend Story:** 6.2

**Request:**
```json
{
  "plan_id": "pro_monthly",
  "duration_months": 3
}
```

**Response (Success):**
```json
{
  "checkout_url": "https://checkout.stripe.com/pay/cs_live_...",
  "admin_approval_mode": false
}
```

**Response (Admin Approval Fallback):**
```json
{
  "checkout_url": "",
  "admin_approval_mode": true
}
```

---

## UI Elements

**Colors:**
- Primary action: Indigo (button active)
- Background: Zinc/Slate dark
- Accents: Emerald for savings badges

**Typography:**
- Font: Inter
- h1: text-3xl font-bold
- Body: text-sm

**Icons:**
- Zap (lucide-react) for purchase button

**Components:**
- Button (shadcn/ui)
- Card, CardHeader, CardTitle, CardContent
- Badge

---

## State Flow

```
Component Mount
  ├─ selectedDuration = 1 (default)
  └─ isLoading = false

User Clicks Duration Button
  └─ setSelectedDuration(3)

User Clicks Purchase
  ├─ setIsLoading(true)
  ├─ Call API
  ├─ API success
  │   └─ window.location.href = checkout_url
  └─ API error
      ├─ toast.error(...)
      └─ setIsLoading(false)
```

---

## Error Scenarios

| Scenario | Handling |
|----------|----------|
| Stripe not configured | Show info toast: "not currently available" |
| Network error | Show error toast: "Unable to start gift checkout" |
| Invalid response | Show error toast: "Failed to create session" |
| Spam clicks | Ignored (loading state prevents duplicates) |

---

## Testing Checklist

- [ ] Duration buttons render + display correct prices
- [ ] Savings badges show only for 3/6/12 month options
- [ ] Clicking button updates selectedDuration
- [ ] Purchase button calls createGiftCheckout() with correct params
- [ ] Success → redirects to checkout_url
- [ ] Error → shows toast, button re-enabled
- [ ] Loading state prevents duplicate API calls
- [ ] Mobile responsive (2-column grid)
- [ ] Design system colors + typography
- [ ] Keyboard navigation works
- [ ] No console errors

---

## Success Criteria (From Epic)

✅ User can access `/dashboard/[id]/gift`  
✅ Page displays duration options (1/3/6/12 months)  
✅ Prices shown: $20/$54/$96/$168  
✅ Savings badges displayed  
✅ "Purchase Gift" button redirects to Stripe  
✅ Admin approval mode handled gracefully  
✅ Design system compliance (Zinc/Slate + Indigo)  
✅ Error handling with friendly messages  

---

## Dependencies

- **UI Framework:** Next.js (App Router, "use client")
- **State:** React hooks (useState, useMemo, useParams)
- **API:** stripeApiService (existing pattern)
- **Notifications:** sonner (existing)
- **UI Components:** shadcn/ui (Button, Card, Badge)
- **Icons:** lucide-react (Zap)
- **Validation:** Zod (via stripe.types.ts)
- **Styling:** Tailwind CSS (existing)

---

## Related Endpoints

| Story | Endpoint | Purpose |
|-------|----------|---------|
| 6.2 | `POST /api/v1/stripe/create-gift-checkout` | Backend gift checkout (prerequisite) |
| 6.3 | Stripe webhook | Backend fulfillment (automatic) |
| 6.4 | `POST /api/v1/stripe/redeem-gift` | Gift code redemption (Story 6.7) |
| 6.5 | `GET /api/v1/stripe/gift-codes` | Gift history (Story 6.5) |

---

## Reference Files

- **Pattern Reference:** `buy-tokens/page.tsx` (token purchase page)
- **Success Page:** `purchase-success/page.tsx` (already exists, works for gifts)
- **Pricing Page:** `pricing-section.tsx` (plan selector reference)
- **Subscription Content:** `settings/subscription-content.tsx` (subscription info display)

---

## Notes

1. **GIFT_PRICING must match backend** — Update both if prices change
2. **Admin approval fallback** — Works even if Stripe not configured
3. **No user data fetch needed** — No cache invalidation in this page
4. **Success page handles it** — Purchase success page already works
5. **Gift codes sent server-side** — Frontend doesn't need to display code generation
6. **Extensible** — Can easily add more plans (pro_yearly, max_monthly) later

---

## Estimated Timeline

- Types + Service: 30 min
- Page Component: 60 min
- Testing: 60 min
- Integration: 60 min
- Polish + Review: 45 min

**Total:** 4-5 hours

---

## Next Steps

1. ✅ Backend Story 6.2 must be complete (create-gift-checkout endpoint)
2. ✅ Implement types in stripe.types.ts
3. ✅ Add method to StripeApiService
4. ✅ Create gift/page.tsx with full implementation
5. ✅ Test locally with mock API
6. ✅ Connect to real API (Story 6.2)
7. ✅ E2E test with Stripe test cards
8. ✅ Code review + merge
9. ✅ Story 6.7 Frontend: Redeem page next
