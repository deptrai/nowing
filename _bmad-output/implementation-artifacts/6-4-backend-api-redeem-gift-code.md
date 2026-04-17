# Story 6.4: Backend API — Endpoint Redeem Gift Code

Status: done

## Story

As a Người dùng nhận quà,
I want gọi API để redeem gift code và gia hạn subscription của mình,
So that gói PRO được kích hoạt ngay lập tức theo công thức extension mà không cần liên hệ support.

## Acceptance Criteria

1. `POST /api/v1/stripe/redeem-gift` với body `{"code": "GIFT-ABCD-EFGH-IJKL"}` (JWT required) trả về `{"new_expiry": "<ISO datetime>", "plan_id": "pro_monthly"}`.
2. Backend verify: code tồn tại trong `gift_codes`, `status == 'active'`, `expires_at > now()`, `redeemer_id IS NULL`.
3. Nếu hợp lệ: tính `new_expiry = max(user.subscription_current_period_end or now(), now()) + timedelta(days=30 * duration_months)`, update `user.subscription_current_period_end = new_expiry`, `user.plan_id = gift.plan_id`, `user.subscription_status = SubscriptionStatus.ACTIVE`, update `user.monthly_token_limit` và `user.pages_limit` từ `PLAN_LIMITS`, đánh dấu `gift_codes.status = 'redeemed'`, ghi `redeemed_at = now()`, `redeemer_id = user.id`.
4. Nếu code không tồn tại hoặc `redeemer_id IS NOT NULL` hoặc `status != 'active'` → `400 Bad Request` với detail `"Gift code không hợp lệ hoặc đã được sử dụng"`.
5. Nếu code hết hạn (`expires_at <= now()`) → `400 Bad Request` với detail `"Gift code đã hết hạn"`.
6. Toàn bộ update (gift_codes + user) là atomic — dùng `db_session` transaction (không cần explicit `begin()`, SQLAlchemy async session tự manage).
7. `GiftCode`, `GiftCodeStatus` phải được import từ `app.db` (đã thêm ở story 6.3).
8. Schema `RedeemGiftRequest` và `RedeemGiftResponse` được thêm vào `nowing_backend/app/schemas/stripe.py`.

## Tasks / Subtasks

- [x] Thêm Pydantic schemas vào `nowing_backend/app/schemas/stripe.py` (AC: 1, 8)
  - [x] `RedeemGiftRequest(BaseModel)`: `code: str = Field(min_length=1, description="Gift code to redeem")`
  - [x] `RedeemGiftResponse(BaseModel)`: `new_expiry: datetime`, `plan_id: str`

- [x] Thêm `RedeemGiftRequest`, `RedeemGiftResponse` vào import block `stripe_routes.py` (AC: 8)

- [x] Thêm endpoint `POST /redeem-gift` vào `stripe_routes.py` (AC: 1–6)
  - [x] Đặt SAU `create-gift-checkout` endpoint (story 6.2), TRƯỚC `_queue_subscription_approval_request`
  - [x] Dùng `select(GiftCode).where(GiftCode.code == body.code).with_for_update()` — lock row
  - [x] Check `gift is None` hoặc `gift.status != GiftCodeStatus.ACTIVE` hoặc `gift.redeemer_id is not None` → 400
  - [x] Check `gift.expires_at <= datetime.now(UTC)` → 400 "đã hết hạn"
  - [x] Tính `new_expiry` từ công thức extension
  - [x] Update `user` fields: `plan_id`, `subscription_status`, `subscription_current_period_end`, `monthly_token_limit`, `pages_limit`
  - [x] Update `gift` fields: `status = GiftCodeStatus.REDEEMED`, `redeemed_at = now()`, `redeemer_id = user.id`
  - [x] `await db_session.commit()`

- [x] Verify
  - [x] `uv run pytest tests/unit/ -q --ignore=tests/unit/connectors/test_dexscreener_connector.py --ignore=tests/unit/indexing_pipeline/` → **408 passed** (1 pre-existing dexscreener error không liên quan)

## Dev Notes

### Dependency: Story 6.1 (migration 132), Story 6.3 (imports GiftCode/GiftCodeStatus)

`GiftCode` và `GiftCodeStatus` đã được import vào `stripe_routes.py` ở story 6.3. Nếu story 6.3 chưa done, cần tự thêm vào `from app.db import (` block.

### Pattern cho schemas — PHẢI tuân thủ

Thêm vào `nowing_backend/app/schemas/stripe.py`:

```python
from datetime import datetime


class RedeemGiftRequest(BaseModel):
    """Request body for redeeming a gift code."""

    code: str = Field(min_length=1, description="Gift code to redeem (e.g. GIFT-ABCD-EFGH-IJKL).")


class RedeemGiftResponse(BaseModel):
    """Response after successfully redeeming a gift code."""

    new_expiry: datetime
    plan_id: str
```

**Lưu ý:** Cần thêm `from datetime import datetime` vào `stripe.py` nếu chưa có.

### Pattern cho endpoint — PHẢI tuân thủ

```python
@router.post("/redeem-gift", response_model=RedeemGiftResponse)
async def redeem_gift(
    body: RedeemGiftRequest,
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
) -> RedeemGiftResponse:
    """Redeem a gift code and extend the user's subscription.

    The gift code must be active, not expired, and not already redeemed.
    Extension formula: new_expiry = max(current_period_end, now()) + 30 * duration_months days.
    """
    # Lock gift code row to prevent concurrent redemptions
    gift = (
        (
            await db_session.execute(
                select(GiftCode)
                .where(GiftCode.code == body.code)
                .with_for_update()
            )
        )
        .unique()
        .scalar_one_or_none()
    )

    # Validate gift code existence and status
    if (
        gift is None
        or gift.status != GiftCodeStatus.ACTIVE
        or gift.redeemer_id is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gift code không hợp lệ hoặc đã được sử dụng",
        )

    now = datetime.now(UTC)

    # Validate expiry
    if gift.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gift code đã hết hạn",
        )

    # Calculate new subscription expiry
    base_expiry = (
        user.subscription_current_period_end
        if user.subscription_current_period_end and user.subscription_current_period_end > now
        else now
    )
    new_expiry = base_expiry + timedelta(days=30 * gift.duration_months)

    # Update user subscription
    user.plan_id = gift.plan_id
    user.subscription_status = SubscriptionStatus.ACTIVE
    user.subscription_current_period_end = new_expiry

    limits = config.PLAN_LIMITS.get(gift.plan_id, config.PLAN_LIMITS["free"])
    user.monthly_token_limit = limits["monthly_token_limit"]
    user.pages_limit = max(user.pages_used, limits["pages_limit"])
    if user.token_reset_date is None:
        user.token_reset_date = now.date()

    # Mark gift code as redeemed
    gift.status = GiftCodeStatus.REDEEMED
    gift.redeemed_at = now
    gift.redeemer_id = user.id

    await db_session.commit()

    logger.info(
        "Gift code %s redeemed by user %s, new expiry: %s",
        gift.code,
        user.id,
        new_expiry,
    )

    return RedeemGiftResponse(new_expiry=new_expiry, plan_id=gift.plan_id)
```

### Cập nhật import block `stripe_routes.py`

Thêm vào `from app.schemas.stripe import (`:

```python
from app.schemas.stripe import (
    BillingPortalResponse,
    CreateGiftCheckoutRequest,
    CreateGiftCheckoutResponse,
    CreateSubscriptionCheckoutRequest,
    CreateSubscriptionCheckoutResponse,
    CreateTokenTopupRequest,
    CreateTokenTopupResponse,
    PlanId,
    RedeemGiftRequest,         # NEW
    RedeemGiftResponse,        # NEW
    StripeStatusResponse,
    StripeWebhookResponse,
)
```

### Công thức extension subscription — QUAN TRỌNG

```
new_expiry = max(user.subscription_current_period_end, now()) + timedelta(days=30 * duration_months)
```

- Nếu user chưa có subscription (`subscription_current_period_end is None`) → base = `now()`
- Nếu user có subscription còn hạn → base = `subscription_current_period_end` (không mất thời gian còn lại)
- Nếu subscription đã hết hạn (< now()) → base = `now()` (không trừ thời gian đã qua)

### Không cần lock User row

Chỉ cần lock `GiftCode` row để prevent concurrent redemptions. User row update là idempotent với gift code đã bị lock.

### `token_reset_date` — chỉ set nếu None

Giống pattern trong `_update_subscription_from_event()` (line ~403): chỉ set `token_reset_date` nếu `is None`, không reset date hiện có.

### `pages_used` vs `pages_limit`

`user.pages_limit = max(user.pages_used, limits["pages_limit"])` — pattern từ line ~402 trong `_update_subscription_from_event`. Đảm bảo không set limit thấp hơn pages đã dùng.

### Verification command

```bash
cd nowing_backend
uv run pytest tests/unit/ -q \
  --ignore=tests/unit/connectors/test_dexscreener_connector.py \
  --ignore=tests/unit/indexing_pipeline/
```

### Project Structure Notes

- Sửa 2 files:
  - `nowing_backend/app/schemas/stripe.py` — thêm `RedeemGiftRequest`, `RedeemGiftResponse` (và `from datetime import datetime` nếu thiếu)
  - `nowing_backend/app/routes/stripe_routes.py` — thêm import + endpoint

### References

- [Source: nowing_backend/app/routes/stripe_routes.py#385-415] — `_update_subscription_from_event` pattern (update user subscription fields)
- [Source: nowing_backend/app/routes/stripe_routes.py#184-267] — `_fulfill_token_topup` pattern (FOR UPDATE lock)
- [Source: nowing_backend/app/schemas/stripe.py] — schema file pattern
- [Source: nowing_backend/app/config/__init__.py#316-326] — `PLAN_LIMITS` config
- [Source: _bmad-output/planning-artifacts/epics.md#Story-6.4] — AC gốc từ Epic

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- `uv run pytest tests/unit/ -q --ignore=tests/unit/connectors/test_dexscreener_connector.py --ignore=tests/unit/indexing_pipeline/` → 408 passed, 1 pre-existing dexscreener error (không liên quan)

### Completion Notes List

- Schemas `RedeemGiftRequest`/`RedeemGiftResponse` được thêm vào `app/schemas/stripe.py` cạnh `CreateGiftCheckoutResponse` + thêm `from datetime import datetime` top-level.
- Imports `RedeemGiftRequest`, `RedeemGiftResponse` thêm vào `from app.schemas.stripe import (` block trong `stripe_routes.py` (alphabetical order giữa `PlanId` và `StripeStatusResponse`).
- Endpoint `POST /redeem-gift` đặt ngay sau `create-gift-checkout` (line ~937), trước `_queue_subscription_approval_request`.
- `SELECT ... FOR UPDATE` trên `GiftCode` row để serialize redemption (chống double-redeem dưới concurrent requests).
- Validation guard theo đúng spec: gift is None / status != ACTIVE / redeemer_id != NULL → 400 "không hợp lệ"; expires_at <= now → 400 "đã hết hạn".
- Công thức extension: `base = max(subscription_current_period_end, now())`, `new_expiry = base + 30 * duration_months days` — giữ nguyên thời gian subscription còn lại.
- Reuse `_mask_gift_code()` helper từ Story 6.3 để log code an toàn (không leak full code).
- `user.pages_limit = max(user.pages_used, limits["pages_limit"])` — khớp pattern `_update_subscription_from_event`, không set limit thấp hơn pages đã dùng.
- `token_reset_date` chỉ set nếu `None` — không reset date đang active.

### File List

- `nowing_backend/app/schemas/stripe.py` (modified — thêm `RedeemGiftRequest`, `RedeemGiftResponse`)
- `nowing_backend/app/routes/stripe_routes.py` (modified — thêm import + `redeem_gift` endpoint)

## Review Findings (2026-04-17)

Multi-layer adversarial review (Blind Hunter + Edge Case Hunter + Acceptance Auditor). Acceptance Auditor verdict: **PASS** on all 8 ACs. Hunter layers surfaced subscription-state and concurrency risks.

### Patched in this story

- [x] **P1 [Review][Patch] — Stripe subscription state clobber (Critical)** — Redeem unconditionally set `plan_id`, `subscription_status=ACTIVE`, `subscription_current_period_end`. An ACTIVE Stripe subscriber (paying monthly) had `current_period_end` pushed forward and plan overwritten, leaving Stripe and Nowing state desynchronized; a PAST_DUE user was silently "cured". Fix: detect `user.stripe_subscription_id is not None` with live status → extend `current_period_end` only; keep existing `plan_id`/limits untouched so Stripe webhook remains authoritative.
- [x] **P2 [Review][Patch] — User row concurrency race (Critical)** — Two concurrent redemptions of different gift codes by the same user each read the same `subscription_current_period_end`; last-write wins silently voids one gift's extension. Fix: `SELECT ... FOR UPDATE` on the User row before reading `subscription_current_period_end`.
- [x] **P3 [Review][Patch] — `duration_months` not validated (High)** — No floor/ceiling guard; a negative/zero from DB corruption would shrink or no-op the user's expiry. Fix: reject redeem if `gift.duration_months <= 0`.
- [x] **P4 [Review][Patch] — Token counters not reset on redeem (High)** — Existing user with exhausted tokens redeems a gift → `monthly_token_limit` is updated but `tokens_used_this_month` still at cap, so effective tokens = 0. Fix: mirror `_activate_subscription_from_checkout` — reset `tokens_used_this_month=0`, clear `purchased_tokens=0`, advance `token_reset_date` to today.
- [x] **P5 [Review][Patch] — Case + whitespace sensitivity (High)** — Users pasting codes with leading/trailing spaces or lowercase get a spurious "không hợp lệ". Fix: normalize `body.code` via `.strip().upper()` before query; also add `max_length=32` and strip-whitespace to schema.
- [x] **P6 [Review][Patch] — Silent downgrade on plan sunset (Medium)** — `PLAN_LIMITS.get(plan_id, "free")` silently gave free-tier limits if a historical gift plan was removed. Fix: reject redeem if `gift.plan_id not in PLAN_LIMITS` with explicit 400 message directing user to contact support.
- [x] **P7 [Review][Patch] — Whitespace-only codes bypass `min_length=1` (Medium)** — `"   "` passes validator then wastes a DB roundtrip. Fixed by strip-whitespace on schema field + normalization before query.
- [x] **P8 [Review][Patch] — Superfluous `.unique()` call (Nit)** — `.unique()` only applies to joined-eager-loaded collections; removed.

### Deferred (tracked in `deferred-work.md`)

- **HTTP idempotency** — client retry after successful commit sees "đã được sử dụng" instead of success. Needs project-wide `Idempotency-Key` header pattern.
- **Calendar-month accuracy** — `timedelta(days=30 * duration_months)` gives 360 days for a 12-month gift (lose ~5 days). Switch to `dateutil.relativedelta(months=n)` for true calendar math.
- **Mixed i18n** — API errors in Vietnamese, logs/docs in English. Project-wide strategy call.
- **Response enrichment** — add `duration_months` / `extended_by_days` to `RedeemGiftResponse` for cleaner frontend toasts.
- **`redeemer_id` FK `ON DELETE SET NULL` zombie state** — deleted user leaves `status=REDEEMED, redeemer_id=NULL`; risk if future cleanup relies on `redeemer_id IS NULL`.

### Dismissed (with reasoning)

- **Timezone defensive check** — `TIMESTAMP(timezone=True)` guarantees aware datetimes; defensive `replace(tzinfo=UTC)` would mask DB-layer data corruption, not fix it.
- **`pages_limit = max(pages_used, limit)` grandfathering overage** — documented pattern from `_update_subscription_from_event`; intentional design, not this story's concern.
- **Error-message conflation (three failure modes → one 400)** — intentional: don't reveal whether a code exists (anti-enumeration).
- **Strict `<=` / `>` boundary comparisons** — microsecond-precision differences; no practical impact.
- **Self-gift not blocked** — gift economics are user's choice; no fraud signal to act on.

### Verification

- All 8 ACs PASS per Acceptance Auditor.
- `uv run pytest tests/unit/ -q --ignore=tests/unit/connectors/test_dexscreener_connector.py --ignore=tests/unit/indexing_pipeline/` → 408 passed.
