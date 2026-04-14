# Story 5.4: Usage Tracking & Rate Limit Enforcement

## Status
Pre-implementation. Plan mode active. Background agents completed discovery:
- **Agent A (Frontend)**: Document upload UI, 402 quota handling, progress bar components
- **Agent B (Backend)**: Plan limits config, Stripe webhook integration, token quota service

## Key Findings

### Backend Infrastructure (Already Exists)
- **User model columns** (`/surfsense_backend/app/db.py`):
  - `plan_id`, `pages_limit`, `monthly_token_limit`, `tokens_used_this_month`, `subscription_status`
  - `stripe_customer_id`, `stripe_subscription_id`

- **PLAN_LIMITS config** (`/surfsense_backend/app/config/__init__.py:314`):
  ```
  free: {monthly_token_limit: 50K, pages_limit: 500}
  pro_monthly: {monthly_token_limit: 1M, pages_limit: 5K}
  pro_yearly: {monthly_token_limit: 1M, pages_limit: 5K}
  ```

- **Stripe webhook handler** (`/surfsense_backend/app/routes/stripe_routes.py`):
  - `checkout.session.completed`: Sets limits immediately
  - `customer.subscription.created/updated`: Parses price ID → plan_id, applies limits
  - Sets `user.monthly_token_limit`, `user.pages_limit`, resets `tokens_used_this_month`

- **Admin approval** (`/surfsense_backend/app/routes/admin_routes.py:115`):
  - `approve_subscription_request()`: Sets plan, limits, and subscription status

- **Token tracking** (`/surfsense_backend/app/services/token_quota_service.py`):
  - `update_token_usage()`: Increments `tokens_used_this_month`
  - `_maybe_reset_monthly_tokens()`: Auto-resets on date boundary
  - `check_token_quota()`: Raises `TokenQuotaExceededError` on limit breach
  - Mirrors `PageLimitService` pattern

### Frontend Infrastructure (Already Exists)
- **Upload components**:
  - `/surfsense_web/components/sources/DocumentUploadTab.tsx` — Uses `Progress` component
  - `/surfsense_web/components/assistant-ui/document-upload-popup.tsx` — Dialog with error alerts

- **Quota error handling**:
  - `/surfsense_web/app/dashboard/.../new-chat/page.tsx`:
    - `QuotaExceededError` class for 402 status codes
    - Detects `response.status === 402` in SSE stream
    - Fallback: `parsed.errorText?.includes("quota")` or `"token_quota_exceeded"`
    - Shows toast: "Monthly token quota exceeded. Upgrade your plan to continue."

- **Progress bar**: `/surfsense_web/components/ui/progress.tsx` (Shadcn component)

- **User atom**: `/surfsense_web/atoms/user/user-query.atoms.ts` → `currentUserAtom` fetches `/api/v1/users/me`

## Scope of 5.4

### Backend Checklist
1. Add page quota pre-check to document upload route (`/surfsense_backend/app/routes/documents_routes.py`)
   - Before accepting files, call `PageLimitService.check_page_limit()`
   - Estimate pages using `estimate_pages_from_metadata()` for cloud uploads
   - Return 402 if limit exceeded

2. Update document task processing to track actual page usage
   - After processing, call `PageLimitService.update_page_usage()` with actual count

3. Ensure token quota check in chat/message processing (likely already done)
   - Verify `TokenQuotaService.check_token_quota()` is called before message processing

### Frontend Checklist
1. Extend `currentUserAtom` to expose `pages_limit`, `pages_used`, `monthly_token_limit`, `tokens_used_this_month`
   - Or create dedicated `quotaAtom` that fetches `/api/v1/users/quota` (new endpoint)

2. Create `QuotaIndicator` component
   - Uses existing `Progress` component from Shadcn
   - Displays pages and tokens side-by-side or stacked

3. Integrate quota indicator into sidebar or chat-header
   - `/surfsense_web/components/ui/sidebar.tsx` or `/surfsense_web/components/new-chat/chat-header.tsx`

4. Ensure document upload handles 402 errors gracefully
   - Reuse 402/toast pattern from SSE stream

## HTTP 402 Response Pattern (Already in Use)
From `/surfsense_backend/app/routes/new_chat_routes.py` (lines 1149, 1427, 1591):
```python
raise HTTPException(status_code=402, detail="Monthly token quota exceeded")
```

## Next Steps (Implementation Phase)
- Implement backend pre-check in document upload
- Add quota data exposure to `/api/v1/users/me`
- Create frontend quota indicator component
- Test 402 error flow in document uploads
