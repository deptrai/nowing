# Story 6.5: Backend API — Gift History & Admin Fallback

Status: done

## Story

As a Người dùng & Admin,
I want API lấy danh sách gift codes đã mua và cơ chế tạo GiftRequest khi Stripe thất bại,
So that purchaser có thể tra cứu lịch sử quà đã mua, và admin có thể duyệt thủ công khi cần.

## Acceptance Criteria

1. `GET /api/v1/stripe/gift-codes` (JWT required) trả về danh sách gift codes mà `purchaser_id = current_user.id`, sắp xếp `created_at DESC`, với fields: `id`, `code`, `plan_id`, `duration_months`, `status`, `created_at`, `redeemed_at`.
2. `POST /api/v1/stripe/request-gift` (JWT required) với body `{"plan_id": "pro_monthly", "duration_months": 3}` tạo record `gift_requests` với `status='pending'`, trả về `{"request_id": "<uuid>", "message": "Yêu cầu của bạn đang chờ admin xử lý."}`.
3. `POST /api/v1/stripe/request-gift` trả về `409 Conflict` nếu user đã có pending gift request cho cùng `plan_id` + `duration_months`.
4. Schemas `GiftCodeItem`, `GiftCodesResponse`, `RequestGiftRequest`, `RequestGiftResponse` được thêm vào `nowing_backend/app/schemas/stripe.py`.
5. `GiftRequest`, `GiftRequestStatus` được import từ `app.db` vào `stripe_routes.py`.

## Tasks / Subtasks

- [x] Thêm Pydantic schemas vào `nowing_backend/app/schemas/stripe.py` (AC: 4)
  - [x] `GiftCodeItem(BaseModel)`: `id: uuid.UUID`, `code: str`, `plan_id: str`, `duration_months: int`, `status: str`, `created_at: datetime`, `redeemed_at: datetime | None`
  - [x] `GiftCodesResponse(BaseModel)`: `items: list[GiftCodeItem]`, `count: int`
  - [x] `RequestGiftRequest(BaseModel)`: `plan_id: str`, `duration_months: int = Field(ge=1, le=12)`
  - [x] `RequestGiftResponse(BaseModel)`: `request_id: uuid.UUID`, `message: str`

- [x] Thêm `GiftRequest`, `GiftRequestStatus` vào `from app.db import (` block trong `stripe_routes.py` (AC: 5)

- [x] Thêm endpoint `GET /gift-codes` vào `stripe_routes.py` (AC: 1)
  - [x] Query: `select(GiftCode).where(GiftCode.purchaser_id == user.id).order_by(GiftCode.created_at.desc())`
  - [x] Return `GiftCodesResponse`

- [x] Thêm endpoint `POST /request-gift` vào `stripe_routes.py` (AC: 2, 3)
  - [x] Check duplicate: `select(GiftRequest).where(user_id == user.id, plan_id == body.plan_id, duration_months == body.duration_months, status == PENDING)` → 409 nếu có
  - [x] Validate `plan_id` và `duration_months` từ `config.GIFT_PRICING` → 400 nếu không hợp lệ
  - [x] Tạo `GiftRequest(user_id=user.id, plan_id=..., duration_months=...)`, commit, return

- [x] Verify
  - [x] `uv run pytest tests/unit/ -q --ignore=tests/unit/connectors/test_dexscreener_connector.py --ignore=tests/unit/indexing_pipeline/` → **408 passed** (pre-existing dexscreener error unchanged)

## Dev Notes

### Dependency

Story 6.1 (migration 132 — bảng `gift_codes` + `gift_requests`), Story 6.2 (`GIFT_PRICING` config).

### Schemas cần thêm — PHẢI tuân thủ

Thêm vào `nowing_backend/app/schemas/stripe.py`:

```python
import uuid
from datetime import datetime
from typing import Optional


class GiftCodeItem(BaseModel):
    """Single gift code entry in the history list."""

    id: uuid.UUID
    code: str
    plan_id: str
    duration_months: int
    status: str
    created_at: datetime
    redeemed_at: Optional[datetime] = None


class GiftCodesResponse(BaseModel):
    """Response for GET /gift-codes."""

    items: list[GiftCodeItem]
    count: int


class RequestGiftRequest(BaseModel):
    """Request body for creating an admin-approval gift request."""

    plan_id: str
    duration_months: int = Field(ge=1, le=12)


class RequestGiftResponse(BaseModel):
    """Response after creating a gift request."""

    request_id: uuid.UUID
    message: str
```

**Lưu ý:** `uuid` và `Optional` cần được import. Kiểm tra xem `stripe.py` đã có chưa — nếu chưa thêm vào top.

### Pattern cho `GET /gift-codes` — PHẢI tuân thủ

```python
@router.get("/gift-codes", response_model=GiftCodesResponse)
async def get_gift_codes(
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
) -> GiftCodesResponse:
    """List all gift codes purchased by the current user."""
    result = await db_session.execute(
        select(GiftCode)
        .where(GiftCode.purchaser_id == user.id)
        .order_by(GiftCode.created_at.desc())
    )
    gifts = result.scalars().all()
    items = [
        GiftCodeItem(
            id=g.id,
            code=g.code,
            plan_id=g.plan_id,
            duration_months=g.duration_months,
            status=str(g.status),
            created_at=g.created_at,
            redeemed_at=g.redeemed_at,
        )
        for g in gifts
    ]
    return GiftCodesResponse(items=items, count=len(items))
```

### Pattern cho `POST /request-gift` — PHẢI tuân thủ

```python
@router.post("/request-gift", response_model=RequestGiftResponse)
async def request_gift(
    body: RequestGiftRequest,
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
) -> RequestGiftResponse:
    """Create an admin-approval gift request when Stripe is unavailable.

    Used as fallback when create-gift-checkout returns admin_approval_mode=True.
    """
    # Validate plan_id + duration_months
    plan_pricing = config.GIFT_PRICING.get(body.plan_id)
    if not plan_pricing or body.duration_months not in plan_pricing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan_id or duration_months.",
        )

    # Check for existing pending request (same plan + duration)
    existing = await db_session.execute(
        select(GiftRequest)
        .where(GiftRequest.user_id == user.id)
        .where(GiftRequest.plan_id == body.plan_id)
        .where(GiftRequest.duration_months == body.duration_months)
        .where(GiftRequest.status == GiftRequestStatus.PENDING)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bạn đã có yêu cầu đang chờ xử lý cho gói này.",
        )

    req = GiftRequest(
        user_id=user.id,
        plan_id=body.plan_id,
        duration_months=body.duration_months,
    )
    db_session.add(req)
    await db_session.commit()

    logger.info(
        "Gift request created for user %s (plan=%s, months=%d)",
        user.id,
        body.plan_id,
        body.duration_months,
    )

    return RequestGiftResponse(
        request_id=req.id,
        message="Yêu cầu của bạn đang chờ admin xử lý.",
    )
```

### Import `GiftRequest`, `GiftRequestStatus` từ `app.db`

Cập nhật `from app.db import (` (line ~17):

```python
from app.db import (
    GiftCode,
    GiftCodeStatus,
    GiftRequest,              # NEW
    GiftRequestStatus,        # NEW
    SubscriptionRequest,
    SubscriptionRequestStatus,
    SubscriptionStatus,
    User,
    get_async_session,
)
```

### Import schemas mới vào `stripe_routes.py`

Thêm vào `from app.schemas.stripe import (`:

```python
    GiftCodeItem,             # NEW
    GiftCodesResponse,        # NEW
    RequestGiftRequest,       # NEW
    RequestGiftResponse,      # NEW
```

### `scalars().all()` vs `.unique().scalars().all()`

Vì `GiftCode` không có relationship được eager-loaded, dùng `result.scalars().all()` là đủ. Pattern tham khảo: `_fulfill_token_topup` dùng `scalar_one_or_none()` cho single row.

### Admin "approve" flow — KHÔNG implement trong story này

AC epics đề cập "khi admin approve: tạo gift_codes record". Đây là admin backend flow (thường qua admin UI hoặc admin API riêng). Story 6.5 chỉ implement:
1. User tạo `gift_requests` (pending)
2. User xem `gift_codes` history

Admin approval là enhancement sau (không có trong Epic 6 scope).

### `GiftRequest.duration_months` — trường mới so với `SubscriptionRequest`

`SubscriptionRequest` không có `duration_months`. `GiftRequest` có thêm `duration_months` (từ migration 132). Đây là sự khác biệt quan trọng.

### Verification command

```bash
cd nowing_backend
uv run pytest tests/unit/ -q \
  --ignore=tests/unit/connectors/test_dexscreener_connector.py \
  --ignore=tests/unit/indexing_pipeline/
```

### Project Structure Notes

- Sửa 2 files:
  - `nowing_backend/app/schemas/stripe.py` — thêm 4 schemas mới
  - `nowing_backend/app/routes/stripe_routes.py` — thêm imports + 2 endpoints

### References

- [Source: nowing_backend/app/routes/stripe_routes.py#649-705] — `_queue_subscription_approval_request` pattern (duplicate check, GiftRequest creation)
- [Source: nowing_backend/app/db.py#1687-1740] — `SubscriptionRequest` pattern (tương tự `GiftRequest`)
- [Source: nowing_backend/app/schemas/stripe.py] — schema file hiện tại
- [Source: nowing_backend/app/config/__init__.py#324-340] — `GIFT_PRICING` config (từ story 6.2)
- [Source: _bmad-output/planning-artifacts/epics.md#Story-6.5] — AC gốc từ Epic

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Debug Log References

- `uv run pytest tests/unit/ -q --ignore=tests/unit/connectors/test_dexscreener_connector.py --ignore=tests/unit/indexing_pipeline/` → 408 passed, 1 pre-existing unrelated dexscreener error.

### Completion Notes List

- Added 4 schemas (`GiftCodeItem`, `GiftCodesResponse`, `RequestGiftRequest`, `RequestGiftResponse`) to `app/schemas/stripe.py`; `uuid` + `datetime` imports already present from Story 6.4.
- Added `GiftRequest`, `GiftRequestStatus` to the `from app.db import (...)` block (alphabetical after `GiftCodeStatus`).
- Added 4 schemas to the `from app.schemas.stripe import (...)` block.
- Implemented `GET /gift-codes`: `select(GiftCode).where(purchaser_id == user.id).order_by(created_at.desc())`, maps enum status to string via `g.status.value` fallback, returns `GiftCodesResponse(items=..., count=len(items))`.
- Implemented `POST /request-gift`:
  - Validates `config.GIFT_PRICING[plan_id][duration_months]` existence → 400 if invalid.
  - Checks existing `PENDING` `GiftRequest` by `(user_id, plan_id, duration_months)` → 409 if duplicate.
  - Creates `GiftRequest`, commits, refreshes to populate `id`, returns `RequestGiftResponse(request_id, message="Yêu cầu của bạn đang chờ admin xử lý.")`.
- Placement: both endpoints inserted immediately after `redeem_gift` (line 1070) and before `_queue_subscription_approval_request`.
- No admin-approve flow included (explicitly out of scope per spec).

### File List

- `nowing_backend/app/schemas/stripe.py` (modified — thêm `GiftCodeItem`, `GiftCodesResponse`, `RequestGiftRequest`, `RequestGiftResponse`)
- `nowing_backend/app/routes/stripe_routes.py` (modified — thêm imports + `get_gift_codes`, `request_gift` endpoints)

### Review Findings

_Three-layer adversarial review (Blind Hunter + Edge Case Hunter + Acceptance Auditor) on 2026-04-17. All 5 ACs Pass per auditor. 0 decision-needed (best-practice auto-resolved), 7 patches queued, 4 deferred, 6 dismissed._

- [x] [Review][Patch] Simplify dead-branch enum coercion in `get_gift_codes` → use `status=g.status.value` directly [`nowing_backend/app/routes/stripe_routes.py:1091`]
- [x] [Review][Patch] Replace `plan_id: str` with `PlanId` enum in `RequestGiftRequest` (Epic 5 convention) [`nowing_backend/app/schemas/stripe.py:87`]
- [x] [Review][Patch] Pin `duration_months` to `Literal[1, 3, 6, 12]` matching `GIFT_PRICING` keys; eliminate ambiguous 400 [`nowing_backend/app/schemas/stripe.py:88`]
- [x] [Review][Patch] Add Stripe-unavailable guard to `request_gift` (enforce docstring promise of "fallback when Stripe unavailable") [`nowing_backend/app/routes/stripe_routes.py:1101-1112`]
- [x] [Review][Patch] Serialize concurrent `request_gift` via `SELECT ... FOR UPDATE` on User row (mirror `redeem_gift` pattern) to prevent double-submit race [`nowing_backend/app/routes/stripe_routes.py:1117`]
- [x] [Review][Patch] Add `limit`/`offset` pagination to `get_gift_codes` (default 50, max 200); prevents unbounded query [`nowing_backend/app/routes/stripe_routes.py:1074-1084`]
- [x] [Review][Patch] Add `expires_at: datetime` to `GiftCodeItem` (enables Story 6.6 near-expiry UX; column already exists) [`nowing_backend/app/schemas/stripe.py:65-75`]

- [x] [Review][Defer] `GiftRequest.updated_at` has no autoupdate trigger — needs DB migration + admin workflow (out of Story 6.5 scope) [`nowing_backend/app/db.py:1832`] — deferred, pre-existing
- [x] [Review][Defer] No REJECTED resubmission cooldown (mirror `_queue_subscription_approval_request` 24h pattern) — admin reject flow not yet implemented [`nowing_backend/app/routes/stripe_routes.py:1117`] — deferred, out of scope
- [x] [Review][Defer] No rate limiting on `request_gift` — infra concern (no cross-cutting limiter in codebase yet) [`nowing_backend/app/routes/stripe_routes.py:1100`] — deferred, infra
- [x] [Review][Defer] No structured audit row/table for admin-approval workflow — requires new audit table [`nowing_backend/app/routes/stripe_routes.py:1138`] — deferred, infra

**Dismissed (for transparency):**
- Gift code plaintext in `get_gift_codes` listing — **intended** behavior: purchaser owns the codes they bought and needs them visible to gift to recipients.
- Vietnamese copy in API response bodies — consistent with existing `redeem_gift` / Epic 5 conventions; i18n refactor is a separate cross-cutting concern.
- `count=len(items)` redundant — AC4 + spec pattern explicitly specify `count: int` in `GiftCodesResponse`; honored verbatim.
- Auditor D1: `Optional[datetime]` vs `datetime | None` — PEP 604 modern equivalent.
- Auditor D3: extra `await db_session.refresh(req)` — defensive no-op, zero cost.
- Auditor D4: `f"..."` → `"..."` (no interpolation) — spec typo already corrected.
