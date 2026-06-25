# Story 6.6: Frontend Gift Purchase Page
## Comprehensive Implementation Guide

**Epic:** Epic 6 - Gift Subscription  
**Story:** 6.6  
**Status:** In Planning  
**Date:** 2026-04-16

---

## Table of Contents

1. [Overview](#overview)
2. [Acceptance Criteria](#acceptance-criteria)
3. [Architecture & Design Patterns](#architecture--design-patterns)
4. [Frontend Directory Structure](#frontend-directory-structure)
5. [Detailed Implementation Steps](#detailed-implementation-steps)
6. [API Integration Points](#api-integration-points)
7. [Type Definitions](#type-definitions)
8. [Component Specifications](#component-specifications)
9. [Pages & Routes](#pages--routes)
10. [State Management](#state-management)
11. [Error Handling & Edge Cases](#error-handling--edge-cases)
12. [UI/UX Requirements](#uiux-requirements)
13. [Testing Checklist](#testing-checklist)

---

## Overview

**Story 6.6** implements the **Gift Purchase Page** allowing authenticated users to purchase PRO subscriptions as gifts for others via Stripe one-time payment. This is a **frontend-focused story** that:

- Creates a new page `/dashboard/[search_space_id]/gift` for logged-in users
- Allows selection of plan duration (1, 3, 6, or 12 months)
- Displays pricing dynamically based on GIFT_PRICING config
- Integrates with existing Stripe API service for gift checkout creation
- Redirects to Stripe Checkout for payment
- Handles success/error flows gracefully
- Follows existing Nowing design patterns (Zinc/Slate, Indigo accent, Inter font)

**Predecessor:** Story 6.2 (Backend API for gift checkout) must be complete before this story.

---

## Acceptance Criteria

**Given** a logged-in user navigates to `/dashboard/[search_space_id]/gift`

**When** the page loads

**Then** the following are displayed:
1. ✅ Clear heading: "Gift a Subscription"
2. ✅ Subheading explaining what they're doing
3. ✅ Plan selection (PRO Monthly only for initial launch)
4. ✅ Duration selector with options: 1 month, 3 months, 6 months, 12 months
5. ✅ Price display for each duration (aligned with backend GIFT_PRICING):
   - 1 month: $20
   - 3 months: $54
   - 6 months: $96
   - 12 months: $168
6. ✅ Savings indicator for multi-month purchases (e.g., "Save $6 compared to 3x monthly")
7. ✅ "Purchase Gift" button (disabled until valid selection)
8. ✅ UI follows design system (Zinc/Slate dark mode, Indigo accent buttons, Inter font)

**When** user clicks "Purchase Gift"

**Then**:
1. ✅ Button enters loading state ("Purchasing…")
2. ✅ Frontend calls `POST /api/v1/stripe/create-gift-checkout` with `{plan_id: "pro_monthly", duration_months: N}`
3. ✅ On success: Automatically redirect to returned `checkout_url` (Stripe Checkout)
4. ✅ On error: Display toast error message, keep button enabled for retry
5. ✅ Network errors handled gracefully with "Unable to connect" message

**When** user completes payment on Stripe Checkout

**Then**:
1. ✅ Stripe redirects to `/purchase-success?session_id={...}`
2. ✅ Success page displays confirmation message
3. ✅ User can see gift code (displayed inline or in user-settings)
4. ✅ Buttons to: "Back to Dashboard" and "View My Gift Codes"

**When** user is not logged in and tries to access `/dashboard/[search_space_id]/gift`

**Then**:
1. ✅ Redirect to login page (Next.js middleware should handle this)

**When** API returns error (Stripe not configured, invalid plan, etc.)

**Then**:
1. ✅ Display user-friendly error toast
2. ✅ For "Stripe not configured": "Payment processing is not available. Contact admin."
3. ✅ Log error server-side for debugging

---

## Architecture & Design Patterns

### Pattern 1: Page Structure (Following `buy-tokens/page.tsx`)

The gift purchase page follows the exact same pattern as the existing token purchase flow:

```
[search_space_id]/
  ├── buy-tokens/
  │   └── page.tsx          ← Existing reference pattern
  ├── gift/                 ← NEW
  │   └── page.tsx          ← To create
  └── purchase-success/
      └── page.tsx          ← Existing redirect target
```

### Pattern 2: Stripe Integration (Using StripeApiService)

The **Stripe API service** is located at:
```
lib/apis/stripe-api.service.ts
```

Current methods:
- `createTokenTopupCheckout()` - token purchases
- `getBillingPortal()` - subscription management
- `getStatus()` - check if Stripe enabled

**New method needed:**
- `createGiftCheckout(plan_id, duration_months)` - gift purchase checkout

### Pattern 3: Component Architecture

```
gift/page.tsx (client component)
└─ "use client"
   ├─ useParams() → search_space_id
   ├─ useAtomValue(currentUserAtom) → user auth check
   ├─ useState() → duration selection, loading state
   ├─ stripeApiService.createGiftCheckout() → API call
   └─ Toast notifications via sonner
```

### Pattern 4: Design System Consistency

**Reference:** `buy-tokens/page.tsx` and `pricing-section.tsx`

- **Colors:** Zinc/Slate dark mode background, Indigo primary buttons
- **Typography:** Inter font family, text-sm/text-base/text-2xl hierarchy
- **Components:** shadcn/ui (Button, Card, Input, Badge)
- **Spacing:** Consistent p-4, gap-2, py-8 patterns
- **Icons:** lucide-react (Zap for purchase action)
- **Animations:** <150ms transitions, smooth hover states

---

## Frontend Directory Structure

```
nowing_web/
├── app/
│   └── dashboard/
│       └── [search_space_id]/
│           ├── buy-tokens/
│           │   └── page.tsx          ← Reference pattern
│           ├── gift/
│           │   └── page.tsx          ← NEW FILE TO CREATE
│           ├── purchase-success/
│           │   └── page.tsx          ← Existing success redirect
│           └── purchase-cancel/
│               └── page.tsx
├── lib/
│   ├── apis/
│   │   └── stripe-api.service.ts     ← MODIFY: add createGiftCheckout()
│   └── ...
├── contracts/
│   └── types/
│       └── stripe.types.ts           ← MODIFY: add gift request/response types
├── components/
│   ├── ui/
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── badge.tsx
│   │   └── ...
│   └── ...
└── ...
```

---

## Detailed Implementation Steps

### Step 1: Update Stripe Types (`stripe.types.ts`)

**File:** `/Users/luisphan/Documents/GitHub/Nowing/nowing_web/contracts/types/stripe.types.ts`

**Add to existing exports:**

```typescript
// Gift Checkout Request/Response
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

**Reasoning:** 
- `plan_id` enum constrains to valid gift plans (initially "pro_monthly" only, but extensible)
- `duration_months` limits 1-12 months to prevent invalid durations
- Response matches existing pattern: `checkout_url` + `admin_approval_mode` fallback
- All types use Zod validation consistent with existing codebase

---

### Step 2: Update Stripe API Service (`stripe-api.service.ts`)

**File:** `/Users/luisphan/Documents/GitHub/Nowing/nowing_web/lib/apis/stripe-api.service.ts`

**Add new method after `createTokenTopupCheckout`:**

```typescript
import {
  type CreateGiftCheckoutRequest,
  type CreateGiftCheckoutResponse,
  createGiftCheckoutResponse,
  // ... existing imports
} from "@/contracts/types/stripe.types";

class StripeApiService {
  // Existing methods...

  createGiftCheckout = async (
    request: CreateGiftCheckoutRequest
  ): Promise<CreateGiftCheckoutResponse> => {
    return baseApiService.post(
      "/api/v1/stripe/create-gift-checkout",
      createGiftCheckoutResponse,
      {
        body: request,
      }
    );
  };

  // ... rest of existing methods
}
```

**Reasoning:**
- Follows identical pattern to `createTokenTopupCheckout`
- Uses same `baseApiService` infrastructure (auth headers, response validation)
- Zod schema ensures response is typed correctly before returning to component
- Endpoint must match backend route (Story 6.2): `/api/v1/stripe/create-gift-checkout`

---

### Step 3: Create Gift Purchase Page (`gift/page.tsx`)

**File:** `/Users/luisphan/Documents/GitHub/Nowing/nowing_web/app/dashboard/[search_space_id]/gift/page.tsx`

**Full implementation:**

```typescript
"use client";

import { Zap } from "lucide-react";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import type { CreateGiftCheckoutRequest } from "@/contracts/types/stripe.types";

// Gift pricing configuration (must match backend GIFT_PRICING)
const GIFT_PRICING = {
  1: 20,      // 1 month = $20
  3: 54,      // 3 months = $54 (save $6 vs 3x$20)
  6: 96,      // 6 months = $96 (save $24 vs 6x$20)
  12: 168,    // 12 months = $168 (save $72 vs 12x$20)
} as const;

const DURATION_OPTIONS = [1, 3, 6, 12] as const;

interface DurationOption {
  months: (typeof DURATION_OPTIONS)[number];
  label: string;
  price: number;
  savings: number | null;
}

function calculateSavings(months: number): number | null {
  const monthlyRate = GIFT_PRICING[1];
  const bundlePrice = GIFT_PRICING[months as keyof typeof GIFT_PRICING];
  const regularPrice = monthlyRate * months;
  const savings = regularPrice - bundlePrice;
  return savings > 0 ? savings : null;
}

export default function GiftPage() {
  const params = useParams();
  const searchSpaceId = String(params.search_space_id ?? "");

  // State
  const [selectedDuration, setSelectedDuration] = useState<
    (typeof DURATION_OPTIONS)[number]
  >(1);
  const [isLoading, setIsLoading] = useState(false);

  // Derived data
  const durationOptions: DurationOption[] = useMemo(() => {
    return DURATION_OPTIONS.map((months) => ({
      months,
      label: months === 1 ? "1 month" : `${months} months`,
      price: GIFT_PRICING[months],
      savings: calculateSavings(months),
    }));
  }, []);

  const selectedOption = durationOptions.find(
    (opt) => opt.months === selectedDuration
  )!;

  // Handlers
  const handlePurchase = async () => {
    if (isLoading) return;

    setIsLoading(true);
    try {
      const request: CreateGiftCheckoutRequest = {
        plan_id: "pro_monthly",
        duration_months: selectedDuration,
      };

      const response = await stripeApiService.createGiftCheckout(request);

      // Handle admin approval mode fallback
      if (response.admin_approval_mode) {
        toast.info(
          "Gift purchase processing is not currently available. Please contact support.",
          { duration: 6000 }
        );
        return;
      }

      // Redirect to Stripe Checkout
      if (response.checkout_url) {
        window.location.href = response.checkout_url;
      } else {
        toast.error("Failed to create checkout session. Please try again.");
      }
    } catch (error) {
      console.error("Gift checkout error:", error);
      toast.error("Unable to start gift checkout. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4 py-8">
      <div className="w-full max-w-md space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold">Gift a Subscription</h1>
          <p className="text-sm text-muted-foreground">
            Give your friends or colleagues a PRO subscription for Nowing.
            They'll receive a gift code to activate their account.
          </p>
        </div>

        {/* Plan Info Card */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Choose Duration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* Duration Selection Buttons */}
            <div className="grid grid-cols-2 gap-2">
              {durationOptions.map((option) => (
                <button
                  key={option.months}
                  onClick={() => setSelectedDuration(option.months)}
                  className={`p-3 rounded-lg border-2 transition-colors text-left ${
                    selectedDuration === option.months
                      ? "border-primary bg-primary/10"
                      : "border-muted bg-background hover:border-primary/50"
                  }`}
                >
                  <div className="font-semibold text-sm">{option.label}</div>
                  <div className="text-lg font-bold text-primary">
                    ${option.price}
                  </div>
                  {option.savings !== null && (
                    <Badge
                      variant="secondary"
                      className="mt-1 text-xs bg-emerald-500/20 text-emerald-700 hover:bg-emerald-500/20"
                    >
                      Save ${option.savings}
                    </Badge>
                  )}
                </button>
              ))}
            </div>

            {/* Selected Option Summary */}
            <div className="rounded-md bg-muted px-4 py-3 space-y-1 mt-4">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">
                Summary
              </p>
              <p className="text-sm">
                <span className="font-semibold">PRO Subscription</span>
                {" • "}
                {selectedOption.label}
              </p>
              <p className="text-2xl font-bold text-primary">
                ${selectedOption.price}
              </p>
              {selectedOption.savings !== null && (
                <p className="text-xs text-emerald-600">
                  ✓ You save ${selectedOption.savings} with this bundle
                </p>
              )}
            </div>

            {/* Info Box */}
            <div className="rounded-md bg-blue-500/10 px-3 py-2 border border-blue-500/20">
              <p className="text-xs text-blue-700">
                <span className="font-semibold">📮 How it works:</span>
                {" "}After purchase, you'll receive a gift code to share with the recipient. They can redeem it at{" "}
                <span className="font-mono">/redeem</span> to activate their PRO subscription.
              </p>
            </div>

            {/* Purchase Button */}
            <Button
              className="w-full"
              size="lg"
              disabled={isLoading}
              onClick={handlePurchase}
            >
              <Zap className="h-4 w-4 mr-2" />
              {isLoading ? "Processing…" : `Purchase Gift — $${selectedOption.price}`}
            </Button>
          </CardContent>
        </Card>

        {/* Footer Note */}
        <p className="text-center text-xs text-muted-foreground">
          Payment powered by Stripe. Your transaction is secure and encrypted.
        </p>
      </div>
    </div>
  );
}
```

**Detailed Explanation:**

| Section | Purpose | Notes |
|---------|---------|-------|
| **Imports** | Dependencies | `lucide-react` for Zap icon, `sonner` for toasts, shadcn/ui for components |
| **GIFT_PRICING** | Static config | Must match backend Story 6.2. Centralized for easy updates. |
| **DURATION_OPTIONS** | Available durations | Constrained tuple for type safety. |
| **calculateSavings()** | Utility function | Computes discount vs monthly rate for UI display. |
| **DurationOption interface** | Type definition | Ensures consistent data shape across component. |
| **selectedDuration state** | Duration selection | Starts at 1 month as sensible default. |
| **isLoading state** | Loading state | Prevents double-clicks, shows "Processing…" text. |
| **useMemo()** | Optimization | Recalculates only when DURATION_OPTIONS changes (never in practice). |
| **handlePurchase()** | Main logic | Calls API service, handles fallback modes, redirects to Stripe. |
| **Layout** | Structure | Centered card, matches buy-tokens pattern exactly. |
| **Duration Buttons** | Selection UI | Grid 2-column layout, visual feedback on active state. |
| **Summary Box** | Confirmation | Shows selection + savings badge. |
| **Info Box** | User guidance | Explains gift code flow in friendly blue box. |
| **Purchase Button** | Call-to-action | Shows price dynamically, disabled during loading. |

---

### Step 4: Verify Success Page Compatibility (`purchase-success/page.tsx`)

**File:** `/Users/luisphan/Documents/GitHub/Nowing/nowing_web/app/dashboard/[search_space_id]/purchase-success/page.tsx`

**Status:** ✅ Already exists and works for all checkout types (tokens, subscriptions, gifts)

The existing success page:
1. ✅ Invalidates user query cache on mount (refetches updated profile)
2. ✅ Shows confirmation message ("Tokens added!")
3. ✅ Links back to dashboard and buy-tokens page
4. ✅ Works generically for any checkout type

**NO CHANGES NEEDED** — this page handles all Stripe success flows.

---

## API Integration Points

### Endpoint 1: Create Gift Checkout

**Method:** `POST`  
**Path:** `/api/v1/stripe/create-gift-checkout`  
**Status:** Implemented in Story 6.2 (Backend)

**Request:**
```typescript
{
  plan_id: "pro_monthly",      // enum: pro_monthly | pro_yearly
  duration_months: 3           // int: 1-12
}
```

**Response:**
```typescript
{
  checkout_url: "https://checkout.stripe.com/pay/cs_live_...",
  admin_approval_mode: false   // true if Stripe not configured
}
```

**Error Handling (Frontend):**
- `400 Bad Request` — Invalid plan_id or duration_months
- `401 Unauthorized` — User not authenticated
- `503 Service Unavailable` — Stripe not configured (admin_approval_mode=true)
- `5xx` — Network/API error → show generic error toast

### Endpoint 2: Stripe Webhook (Backend only)

**Status:** Implemented in Story 6.3 (Backend)  
**Frontend Impact:** None (backend-to-backend)

The webhook processes `checkout.session.completed` with `metadata.purchase_type="gift"` and:
1. Generates gift code (`GIFT-XXXX-XXXX-XXXX`)
2. Stores in `gift_codes` table
3. Sends code to purchaser via email (or success page)

---

## Type Definitions

### Stripe Types File

**Location:** `nowing_web/contracts/types/stripe.types.ts`

**Current Types:**
```typescript
export type CreateTokenTopupRequest = { amount_usd: number; search_space_id: number }
export type CreateTokenTopupResponse = { checkout_url: string; admin_approval_mode: bool }
export type BillingPortalResponse = { url: string }
export type StripeStatusResponse = { stripe_enabled: bool }
```

**New Types to Add:**
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

**Rationale:**
- Zod schemas provide runtime validation
- TypeScript inference ensures compile-time type safety
- Consistent with existing stripe.types.ts pattern
- Extensible for future plans (pro_yearly, max_monthly, etc.)

---

## Component Specifications

### Main Component: GiftPage

**File:** `app/dashboard/[search_space_id]/gift/page.tsx`

**Props:** None (uses `useParams()` to extract `search_space_id`)

**State:**
- `selectedDuration: 1 | 3 | 6 | 12` — Currently selected duration
- `isLoading: boolean` — API call in progress

**Effects:** None required (no data fetching on mount)

**Exports:** Default export `GiftPage`

**Key Features:**
1. ✅ Responsive grid layout (2 columns on mobile)
2. ✅ Visual feedback on duration selection
3. ✅ Dynamic price display with savings indicator
4. ✅ Loading state on button during API call
5. ✅ Toast notifications for success/error
6. ✅ Automatic redirect to Stripe on success

---

## Pages & Routes

### Route 1: Gift Purchase Page

**Path:** `/dashboard/[search_space_id]/gift`  
**Component:** `app/dashboard/[search_space_id]/gift/page.tsx`  
**Access:** Authenticated users only  
**Layout:** Dashboard layout with header, sidebar

**Navigation paths TO this page:**
- User manual entry: `/dashboard/123/gift`
- From subscription-content.tsx: Link button (TBD in Story 6.7 frontend)
- From pricing page: "Gift a Subscription" button (TBD in future)

**Navigation paths FROM this page:**
- Success: Redirect to Stripe Checkout URL (external)
- Cancel: User manually back button
- After Stripe success: → `/purchase-success?session_id=...` (Stripe redirect)

### Route 2: Purchase Success Page (Existing)

**Path:** `/dashboard/[search_space_id]/purchase-success`  
**Component:** `app/dashboard/[search_space_id]/purchase-success/page.tsx`  
**Status:** ✅ Already exists, works for gifts

**What it does:**
1. Invalidates user cache (refetch user profile with updated gift codes)
2. Shows success card with checkmark
3. Links: "Back to Dashboard" + "Buy More Tokens"
4. TBD: Could add "View Gift Codes" link for gift purchases

---

## State Management

### Query State (User Profile)

**Location:** `atoms/user/user-query.atoms.ts`  
**Atom:** `currentUserAtom`  
**Usage:** NOT used in this page (no auth check needed, middleware handles)

**After payment success:** 
- Purchase success page calls `queryClient.invalidateQueries({ queryKey: USER_QUERY_KEY })`
- User sidebar updates to show new subscription status
- No local state refresh needed in gift page itself

### UI State (Local to Page)

**selectedDuration:**
```typescript
const [selectedDuration, setSelectedDuration] = useState<1 | 3 | 6 | 12>(1);
```
- Represents current duration choice
- Updated on button click
- Resets to 1 when component mounts (stateless across navigations)

**isLoading:**
```typescript
const [isLoading, setIsLoading] = useState(false);
```
- `true` while API call in progress
- Disables button and shows "Processing…"
- Reset after API completes (success or error)

---

## Error Handling & Edge Cases

### Case 1: API Error (Stripe Misconfigured)

**Scenario:** Backend returns `admin_approval_mode: true`

**Handling:**
```typescript
if (response.admin_approval_mode) {
  toast.info(
    "Gift purchase processing is not currently available. Please contact support.",
    { duration: 6000 }
  );
  return; // Exit early, keep button enabled
}
```

**User Experience:**
- Friendly info toast (not error—expected in dev/admin scenarios)
- Button remains enabled for retry
- No crash or navigation

### Case 2: Network Error (No Response)

**Scenario:** `stripeApiService.createGiftCheckout()` throws error

**Handling:**
```typescript
catch (error) {
  console.error("Gift checkout error:", error);
  toast.error("Unable to start gift checkout. Please try again.");
}
```

**User Experience:**
- Console logs error for debugging
- User sees friendly error toast
- Button re-enabled for retry
- Page stays in-place

### Case 3: Invalid URL Parameters

**Scenario:** User visits `/dashboard/invalid/gift`

**Handling:**
```typescript
const searchSpaceId = String(params.search_space_id ?? "");
// searchSpaceId = "" if missing
// Button still works but API will likely reject
```

**Mitigation:** Next.js middleware should validate `[search_space_id]` before rendering

### Case 4: User Not Authenticated

**Scenario:** Unauthenticated user navigates to `/dashboard/[id]/gift`

**Handling:** Next.js middleware (existing) redirects to login

**No changes needed** — middleware handles this globally

### Case 5: User Spam-Clicks Purchase Button

**Scenario:** User clicks button multiple times rapidly

**Handling:**
```typescript
const handlePurchase = async () => {
  if (isLoading) return;  // ← Exit early if already loading
  setIsLoading(true);
  // ... API call ...
  setIsLoading(false);
}
```

**User Experience:**
- First click: Button disables, shows "Processing…"
- Subsequent clicks: Ignored (prevented by `if (isLoading) return`)
- No duplicate API calls

### Case 6: Window Redirect to Stripe Fails

**Scenario:** `window.location.href = checkout_url` blocked by browser

**Very unlikely** but mitigated by:
```typescript
if (response.checkout_url) {
  window.location.href = response.checkout_url;  // Usually works
} else {
  toast.error("Failed to create checkout session. Please try again.");
}
```

---

## UI/UX Requirements

### Design System Compliance (UX-DR1)

**Color Palette:**
- Background: `bg-background` (Zinc/Slate dark #09090b)
- Text: `text-foreground` (light gray)
- Muted: `text-muted-foreground`
- Primary action: `bg-primary` (Indigo accent)
- Secondary: `bg-secondary` / `bg-muted`

**Typography:**
- Font family: Inter (via Tailwind default)
- Heading: `text-3xl font-bold` (h1)
- Subheading: `text-sm text-muted-foreground`
- Body: `text-sm` (default)
- Labels: `text-xs uppercase tracking-wide`

**Components:**
- Buttons: `Button` from shadcn/ui
- Cards: `Card`, `CardHeader`, `CardTitle`, `CardContent`
- Badges: `Badge` for "Save $X" labels
- Icons: `Zap` (lucide-react)

**Spacing:**
- Page container: `px-4 py-8` (mobile-friendly padding)
- Card spacing: `space-y-6` (vertical gaps)
- Internal card: `pb-3`, `px-4 py-3`
- Button grid: `grid-cols-2 gap-2`

### Responsive Design

**Mobile (< 640px):**
- Full width card (px-4 padding)
- 2-column duration grid (fits nicely on small screens)
- Large touch targets (h-auto py-2 on buttons)

**Tablet/Desktop (≥ 640px):**
- `max-w-md` card (centered, fixed width)
- Same 2-column grid works well
- Hover effects on duration buttons

### Animation/Interaction

**Button Loading State:**
- Text changes: "Purchase Gift — $20" → "Processing…"
- Disabled attribute: ✓ (`disabled={isLoading}`)
- No spinner icon (keep it simple)

**Toast Notifications:**
- Error: Red background, 4s duration (sonner default)
- Info: Blue background, 6s duration
- Success: Green (not used in this page, but available)

**Transitions:**
- Duration button hover: `transition-colors` (fast)
- No heavy animations (keep TTFT low per NFR-P1)

### Accessibility

**Semantic HTML:**
- `<h1>` for page title
- `<button>` elements for interactions
- `<div role="group">` for duration options (TBD if needed)

**Keyboard Navigation:**
- Tab through duration buttons
- Tab to purchase button
- Space/Enter to activate

**Color Contrast:**
- All text meets WCAG AA standards (shadcn/ui components)
- Savings badge: Green on light background (sufficient contrast)

---

## Testing Checklist

### Unit Tests (Vitest)

- [ ] **Duration Options Rendering**
  - ✓ All 4 duration buttons render
  - ✓ Correct prices display ($20, $54, $96, $168)
  - ✓ Savings badges show only for multi-month options

- [ ] **Selection State**
  - ✓ Clicking duration button updates `selectedDuration`
  - ✓ Active button shows primary color
  - ✓ Inactive buttons show muted color

- [ ] **API Integration**
  - ✓ `handlePurchase()` calls `stripeApiService.createGiftCheckout()` with correct params
  - ✓ Success response redirects to `checkout_url`
  - ✓ Admin approval mode shows info toast
  - ✓ Network error shows error toast

- [ ] **Loading State**
  - ✓ Button disabled during API call
  - ✓ Button text changes to "Processing…"
  - ✓ Clicking while loading doesn't trigger duplicate API calls
  - ✓ Loading state clears after success or error

### Integration Tests (Playwright)

- [ ] **User Flow: Full Purchase**
  1. Navigate to `/dashboard/123/gift` ✓
  2. Page loads (no errors in console) ✓
  3. All duration options visible ✓
  4. Select 3-month option ✓
  5. Price updates to $54 ✓
  6. Click "Purchase Gift" ✓
  7. Button enters loading state ✓
  8. (Mock API response) ✓
  9. Redirect to Stripe Checkout URL ✓

- [ ] **User Flow: Error Handling**
  1. Mock API error response ✓
  2. Error toast appears ✓
  3. Button re-enabled for retry ✓
  4. Clicking Purchase again works ✓

- [ ] **Mobile Responsiveness**
  1. Page renders on mobile viewport (375px) ✓
  2. Duration buttons stack in 2-column grid ✓
  3. Card text readable ✓
  4. Button clickable ✓

- [ ] **Authentication**
  1. Unauthenticated user → redirects to login ✓
  2. Authenticated user → page loads ✓

### E2E Tests (End-to-End)

- [ ] **Live Stripe Integration (Staging)**
  1. Navigate to `/dashboard/123/gift` ✓
  2. Select duration ✓
  3. Click "Purchase Gift" ✓
  4. Redirected to Stripe Checkout ✓
  5. Test payment flow (use Stripe test card 4242...) ✓
  6. Redirect to `/purchase-success` ✓
  7. Success message displays ✓
  8. Verify backend gift code created ✓

- [ ] **Admin Approval Fallback (Staging)**
  1. Disable Stripe API key ✓
  2. Navigate to `/dashboard/123/gift` ✓
  3. Click "Purchase Gift" ✓
  4. Info toast: "not currently available" ✓
  5. Button re-enabled ✓

### Manual Testing Checklist

- [ ] **Visual Design**
  - [ ] Colors match Zinc/Slate + Indigo palette
  - [ ] Typography is Inter font
  - [ ] Spacing/padding looks balanced
  - [ ] No layout shift on button state change
  - [ ] Loading spinner smooth (if any)

- [ ] **Error Messages**
  - [ ] Error toast text is user-friendly
  - [ ] Info toast text explains situation
  - [ ] No technical jargon in user-facing messages

- [ ] **Browser Compatibility**
  - [ ] Chrome ✓
  - [ ] Firefox ✓
  - [ ] Safari ✓
  - [ ] Edge ✓

- [ ] **Performance**
  - [ ] Page loads <1s
  - [ ] Button click → API call <200ms
  - [ ] No console errors
  - [ ] No memory leaks (DevTools check)

---

## Implementation Order

### Phase 1: Type & Service Setup (30 min)

1. ✅ Update `stripe.types.ts` with `CreateGiftCheckoutRequest/Response`
2. ✅ Add `createGiftCheckout()` method to `StripeApiService`
3. ✅ Verify types compile

### Phase 2: Page Creation (1-2 hours)

1. ✅ Create `gift/page.tsx` directory
2. ✅ Write gift page component (use `buy-tokens/page.tsx` as template)
3. ✅ Test locally with mock API
4. ✅ Verify UI/UX matches design system

### Phase 3: Integration Testing (1 hour)

1. ✅ Start backend Story 6.2 (if not done)
2. ✅ Connect to real API endpoint
3. ✅ Test happy path (API success → Stripe redirect)
4. ✅ Test error paths (admin approval mode)
5. ✅ Verify Stripe Checkout redirects correctly

### Phase 4: E2E Testing (1-2 hours)

1. ✅ Run full user flow on staging
2. ✅ Test with Stripe test payment
3. ✅ Verify success page displays
4. ✅ Verify backend gift code created
5. ✅ Check email (gift code sent to purchaser)

### Phase 5: Polish & Review (30-45 min)

1. ✅ Code review (peer or CI)
2. ✅ Accessibility audit
3. ✅ Mobile testing
4. ✅ Documentation update
5. ✅ PR merge to main

**Total Estimated Time:** 4-5 hours

---

## Success Criteria Summary

✅ **Page Structure:**
- Accessible at `/dashboard/[search_space_id]/gift`
- Uses "use client" directive
- Integrates with existing dashboard layout

✅ **Functionality:**
- Displays 4 duration options with prices matching GIFT_PRICING
- Shows savings for multi-month bundles
- Calls `/api/v1/stripe/create-gift-checkout` with correct parameters
- Redirects to Stripe Checkout on success
- Shows toast on error
- Handles admin approval fallback mode

✅ **Design:**
- Follows Zinc/Slate + Indigo color scheme
- Uses Inter font
- Responsive on mobile and desktop
- Consistent with `buy-tokens/page.tsx` patterns

✅ **Error Handling:**
- Network errors handled gracefully
- User-friendly error messages
- Button remains enabled for retry
- No page crashes

✅ **Testing:**
- Unit tests for state management
- Integration tests for API calls
- E2E test on Stripe test environment
- Mobile responsiveness verified

---

## Related Stories

- **Story 6.1:** Database migration (gift_codes, gift_requests tables)
- **Story 6.2:** Backend API for gift checkout (create-gift-checkout endpoint)
- **Story 6.3:** Backend webhook for gift code fulfillment
- **Story 6.4:** Backend API for gift code redemption
- **Story 6.5:** Backend API for gift history
- **Story 6.6:** Frontend gift purchase page ← **THIS STORY**
- **Story 6.7:** Frontend redeem page

---

## Appendix: Reference Implementation (buy-tokens)

The gift purchase page is modeled directly after `buy-tokens/page.tsx`. Key differences:

| Aspect | Buy Tokens | Gift Purchase |
|--------|------------|---------------|
| **Purpose** | User buys tokens for themselves | User buys PRO subscription for others |
| **Input Type** | Custom USD amount | Preset durations (1/3/6/12 months) |
| **Pricing Model** | Fixed rate: $1 = 100K tokens | Bundle pricing: $20/$54/$96/$168 |
| **Plan Selection** | N/A | PRO Monthly only (initially) |
| **Success Redirect** | `/purchase-success` | `/purchase-success` (same) |
| **API Endpoint** | `/create-token-topup-checkout` | `/create-gift-checkout` |
| **UI Layout** | Amount input + quick buttons | Duration card buttons + summary |
| **Stripe Mode** | `payment` (one-time) | `payment` (one-time, same) |

Both use identical:
- ✅ `sonner` toast notifications
- ✅ `shadcn/ui` components (Button, Card)
- ✅ `lucide-react` icons
- ✅ Loading state pattern
- ✅ Error handling pattern
- ✅ Responsive centered layout

---

## Notes for Developer

1. **Stripe Secret Key:** The `/api/v1/stripe/create-gift-checkout` endpoint must be implemented in Story 6.2 (backend). Ensure it returns `CreateGiftCheckoutResponse` with `checkout_url`.

2. **GIFT_PRICING Config:** Keep the hardcoded `GIFT_PRICING` object in `gift/page.tsx` in sync with backend config. When prices change, update both frontend and backend.

3. **Admin Approval Mode:** If Stripe is not configured (e.g., dev/test environment), the API returns `admin_approval_mode: true`. The page handles this gracefully with an info toast.

4. **Gift Code Delivery:** After Stripe payment completes (Story 6.3 webhook), the gift code is generated and sent to the purchaser. The frontend doesn't need to fetch this—it's handled server-side. The user can see their gift codes in user-settings (Story 6.5+ feature).

5. **Future Extensibility:** The current implementation only supports `pro_monthly` gifts. To add `pro_yearly`, `max_monthly`, etc., update:
   - `GIFT_PRICING` object
   - Plan selection UI (currently hardcoded to PRO)
   - Type validation in `stripe.types.ts`
   - Backend GIFT_PRICING config

6. **Testing with Stripe:** Use Stripe test credentials:
   - Test card: `4242 4242 4242 4242`
   - Expiry: Any future date
   - CVC: Any 3 digits
   - Webhook events trigger via Stripe dashboard (CLI in dev)

---

## Sign-Off

**Prepared by:** AI Implementation Guide  
**For Story:** 6.6 (Frontend Gift Purchase Page)  
**Epic:** 6 (Gift Subscription)  
**Date:** 2026-04-16  
**Status:** Ready for Implementation

This guide provides all necessary context, patterns, and specifications for implementing Story 6.6 completely and correctly. Refer to the detailed sections above for code examples, type definitions, and testing procedures.
