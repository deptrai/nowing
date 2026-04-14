# Story 5.4: Usage Tracking & Rate Limit Enforcement — Implementation Plan

**Status**: Plan mode active (no execution yet)  
**Last Updated**: 2026-04-15 03:17 GMT+7  
**Scope**: Document upload quota pre-checking + frontend quota indicator

---

## Phase 1: Backend — Document Upload Quota Pre-Check

### Task 1.1: Add Page Quota Check to Document Upload Route
**File**: `/surfsense_backend/app/routes/documents_routes.py`  
**Target Function**: `create_documents_file_upload()` (line 121)

**Changes**:
1. Instantiate `PageLimitService` with session dependency
2. For each uploaded file:
   - Estimate pages using `PageLimitService.estimate_pages_from_metadata(filename, file_size)`
   - Sum total estimated pages across all files
3. Call `PageLimitService.check_page_limit(user_id, estimated_pages)`
4. If `PageLimitExceededError` is raised, catch and return `HTTPException(status_code=402, detail=error.message)`
5. Otherwise, proceed with document creation

**Pattern Reference**: Use 402 response pattern from `/surfsense_backend/app/routes/new_chat_routes.py` (lines 1149, 1427, 1591)

### Task 1.2: Update Document Task to Track Actual Usage
**File**: `/surfsense_backend/app/tasks/celery_tasks/document_tasks.py`  
**Target Function**: `process_file_upload_task()` or `process_file_upload_with_document_task()`

**Changes**:
1. After successful document processing, retrieve actual page count from processed document
2. Call `PageLimitService.update_page_usage(user_id, actual_pages, allow_exceed=True)`
   - `allow_exceed=True` because we pre-checked, but actual may vary slightly
3. Log the difference between estimated and actual pages

### Task 1.3: Verify Token Quota Check in Chat/Message Route
**File**: `/surfsense_backend/app/routes/new_chat_routes.py`  
**Target**: `chat()` or `create_message()` endpoint

**Changes**:
1. Verify `TokenQuotaService.check_token_quota()` is called before message processing
2. Confirm 402 response is returned on token limit breach
3. No changes expected — this should already be implemented

---

## Phase 2: Frontend — Quota Data & Indicator Component

### Task 2.1: Expose Quota Data from User API
**File**: `/surfsense_backend/app/routes/users_routes.py` or `/surfsense_backend/app/routes/__init__.py`  
**Endpoint**: `GET /api/v1/users/me` (extend existing) or `GET /api/v1/users/quota` (new)

**Option A: Extend `/api/v1/users/me`**
- Add `pages_limit`, `pages_used`, `monthly_token_limit`, `tokens_used_this_month` to response schema

**Option B: Create `/api/v1/users/quota` endpoint**
- New endpoint returns only quota fields
- Lighter weight, can be called separately for real-time updates

**Recommended**: Option A (simpler, reuses existing endpoint)

### Task 2.2: Update User Query Atom
**File**: `/surfsense_web/atoms/user/user-query.atoms.ts`  
**Target**: `currentUserAtom`

**Changes**:
1. Update response type to include quota fields
2. Type definition should match backend UserResponse with quota fields
3. Atom already calls `/api/v1/users/me`, no API call changes needed

### Task 2.3: Create QuotaIndicator Component
**File**: `/surfsense_web/components/ui/quota-indicator.tsx` (new file)

**Component Structure**:
```tsx
interface QuotaIndicatorProps {
  pagesUsed: number;
  pagesLimit: number;
  tokensUsedThisMonth: number;
  monthlyTokenLimit: number;
  compact?: boolean;  // Stack or inline
}

export function QuotaIndicator({ ... }) {
  const pagePercentage = (pagesUsed / pagesLimit) * 100;
  const tokenPercentage = (tokensUsedThisMonth / monthlyTokenLimit) * 100;
  
  return (
    <div>
      <Progress value={pagePercentage} />
      <Progress value={tokenPercentage} />
      {/* Labels: "500 / 5000 pages", "50,000 / 100,000 tokens" */}
    </div>
  );
}
```

**Reuse**: Existing `Progress` component from `/surfsense_web/components/ui/progress.tsx`

### Task 2.4: Integrate QuotaIndicator into Sidebar/Header
**File**: `/surfsense_web/components/ui/sidebar.tsx` or `/surfsense_web/components/new-chat/chat-header.tsx`

**Changes**:
1. Import `QuotaIndicator` component
2. Place in sidebar header or chat header (design decision)
3. Connect to `currentUserAtom` via Jotai hook
4. Pass quota values from atom to component

**Alternative Location**: `/surfsense_web/components/assistant-ui/document-upload-popup.tsx`
- Show quota indicator before upload dialog opens
- Warn user if close to limit

### Task 2.5: Ensure Document Upload 402 Handling
**File**: `/surfsense_web/components/sources/DocumentUploadTab.tsx`

**Changes**:
1. Verify error handling for 402 responses
2. Pattern: Check `response.status === 402`
3. Show toast with quota warning
4. Can reuse SSE error pattern from `/surfsense_web/app/dashboard/.../new-chat/page.tsx`

---

## Phase 3: Testing & Validation

### Test Case 3.1: Document Upload Quota Enforcement
1. User with 400/500 page limit uploads 200-page PDF
2. Expected: 402 error returned before file processing starts
3. User sees toast: "Processing would exceed page limit. Contact admin."

### Test Case 3.2: Token Quota Enforcement
1. User with 50K/100K token limit sends message
2. Expected: If estimated tokens + message > limit, return 402
3. User sees chat error: "Monthly token quota exceeded"

### Test Case 3.3: Quota Indicator Display
1. User visits dashboard with quota indicator visible
2. Indicator shows: "400 / 500 pages", "50,000 / 100,000 tokens"
3. Progress bars reflect usage percentage

### Test Case 3.4: Actual vs Estimated Pages
1. Upload PDF with 50-page estimate but 48 actual pages
2. Verify `update_page_usage()` is called with actual count (48)
3. Verify no over-charging occurs

---

## Implementation Order

**Recommended sequence** (minimizes blocking dependencies):
1. **1.1** — Add page quota check to upload route
2. **2.1** — Expose quota data from user API (quick backend change)
3. **2.2** — Update user atom to include quota fields
4. **2.3** — Create QuotaIndicator component
5. **2.4** — Integrate into sidebar/header
6. **1.2** — Update document task to track actual usage
7. **1.3** — Verify token quota check (should be no-op)
8. **2.5** — Verify document upload 402 handling
9. **Phase 3** — Run test cases

---

## Files to Modify

### Backend (5 files)
- `/surfsense_backend/app/routes/documents_routes.py` — Add pre-check
- `/surfsense_backend/app/tasks/celery_tasks/document_tasks.py` — Update actual usage
- `/surfsense_backend/app/routes/new_chat_routes.py` — Verify (likely no change)
- `/surfsense_backend/app/routes/users_routes.py` — Extend user API (if needed)
- `/surfsense_backend/app/schemas/users.py` — Extend user response schema

### Frontend (5 files)
- `/surfsense_web/atoms/user/user-query.atoms.ts` — Extend atom
- `/surfsense_web/components/ui/quota-indicator.tsx` — **New component**
- `/surfsense_web/components/ui/sidebar.tsx` — Or chat-header
- `/surfsense_web/components/sources/DocumentUploadTab.tsx` — Verify error handling
- `/surfsense_web/app/dashboard/.../new-chat/page.tsx` — Verify SSE error handling

---

## Known Infrastructure in Place

✅ `PageLimitService` — Complete with all estimation methods  
✅ `TokenQuotaService` — Complete with monthly reset logic  
✅ `PLAN_LIMITS` config — Defines free/pro limits  
✅ Stripe webhook integration — Sets limits on subscription  
✅ Admin approval flow — Sets limits when approving  
✅ Progress component — Reusable Shadcn component  
✅ HTTP 402 pattern — Already in use in chat routes  
✅ User atom — Already fetches `/api/v1/users/me`  

---

## Deferred Decisions

- **Quota display location**: Sidebar vs chat-header (design preference)
- **Token quota endpoint**: Extend `/api/v1/users/me` vs create new `/api/v1/users/quota`
- **Page estimation accuracy**: Accept ~10% variance or implement tighter estimation

---

## Estimated Effort

**Backend**: ~2-3 hours (quota check, update tracking, schema changes)  
**Frontend**: ~2-3 hours (atom extension, component creation, integration)  
**Testing**: ~1-2 hours (manual test cases + edge cases)  
**Total**: ~5-8 hours

---

## Success Criteria

- [ ] Document upload returns 402 when page limit would be exceeded
- [ ] User sees quota indicator in UI showing pages and tokens
- [ ] Document task updates actual page usage after processing
- [ ] Chat returns 402 when token limit would be exceeded
- [ ] Toast notifications appear for both quota violations
- [ ] All test cases pass without errors
