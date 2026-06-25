# Story 6.8: Backend API — Admin Approve/Reject Gift Request

Status: done

## Story

As a Superuser (admin),
I want endpoint để list, approve, và reject các `gift_requests` pending,
So that khi Stripe fallback sang admin-approval mode, tôi có thể duyệt thủ công, mint gift code, và link vào request để gửi cho người mua.

## Acceptance Criteria

1. `GET /api/v1/admin/gift-requests?status=<pending|approved|rejected|all>` (JWT + superuser) trả về list `GiftRequestItem` sắp xếp `created_at DESC`. Default `status=pending`. Non-superuser nhận `403`.
2. `POST /api/v1/admin/gift-requests/{request_id}/approve` (JWT + superuser):
   - Lock `gift_requests` row với `SELECT ... FOR UPDATE`.
   - Nếu `status != pending` → `409 Conflict` với detail `"Request is already <status>."`.
   - Nếu không tìm thấy → `404`.
   - Mint new `GiftCode` (pattern `_generate_gift_code`, retry on collision up to 3 lần), set: `status=ACTIVE`, `plan_id=<req.plan_id>`, `duration_months=<req.duration_months>`, `amount_paid=config.GIFT_PRICING[plan_id][duration_months]`, `purchaser_id=<req.user_id>`, `stripe_payment_intent_id=None`, `expires_at=now + 365 days`.
   - Update `gift_request.status=APPROVED`, `gift_request.gift_code_id=<new_code.id>`, `gift_request.updated_at=now`.
   - Commit cả GiftCode + GiftRequest trong cùng transaction (rollback cả 2 nếu fail).
   - Response: `GiftRequestApproveResponse(request_id, gift_code, plan_id, duration_months, gift_code_id)`.
3. `POST /api/v1/admin/gift-requests/{request_id}/reject` (JWT + superuser) với body `{"reason": str | None}`:
   - Lock row, validate `status=pending` (409 nếu không), set `status=REJECTED`, `updated_at=now`.
   - Không tạo gift code.
   - Response: `GiftRequestItem` cập nhật.
4. Schemas `GiftRequestItem`, `GiftRequestListResponse`, `GiftRequestApproveResponse`, `GiftRequestRejectRequest` được thêm vào `nowing_backend/app/schemas/stripe.py` (hoặc `app/schemas/admin.py` nếu có).
5. Endpoints được đặt trong `nowing_backend/app/routes/admin_routes.py` (mirror pattern `approve_subscription_request`).
6. `GiftRequest`, `GiftRequestStatus`, `GiftCode`, `GiftCodeStatus` được import vào `admin_routes.py`.

## Tasks / Subtasks

- [x] Thêm Pydantic schemas vào `nowing_backend/app/schemas/stripe.py` (AC: 4)
  - [x] `GiftRequestItem(BaseModel)`: `id: uuid.UUID`, `user_id: uuid.UUID`, `user_email: str`, `plan_id: str`, `duration_months: int`, `status: str`, `gift_code_id: uuid.UUID | None`, `gift_code: str | None`, `created_at: datetime`, `updated_at: datetime | None`
  - [x] `GiftRequestListResponse(BaseModel)`: `items: list[GiftRequestItem]`, `count: int`
  - [x] `GiftRequestApproveResponse(BaseModel)`: `request_id: uuid.UUID`, `gift_code_id: uuid.UUID`, `gift_code: str`, `plan_id: str`, `duration_months: int`
  - [x] `GiftRequestRejectRequest(BaseModel)`: `reason: str | None = None`

- [x] Extract helper `_mint_gift_code(...)` (AC: 2)
  - [x] Thêm `_mint_gift_code` tại `stripe_routes.py` (trước `_fulfill_gift_purchase`): `(db_session, *, plan_id, duration_months, amount_paid, purchaser_id, stripe_payment_intent_id=None, expires_at=None) -> GiftCode`.
  - [x] Retry-3-lần-on-collision pattern, dùng `flush()` thay `commit()`, trả về `GiftCode` để caller commit cùng transaction.
  - [x] Export từ `stripe_routes.py`, import vào `admin_routes.py`.
  - Note: `_fulfill_gift_purchase` giữ inline loop riêng (error handling khác biệt cho Stripe webhook — log-and-return-200 thay vì raise).

- [x] Thêm endpoints vào `admin_routes.py` (AC: 1, 2, 3, 5)
  - [x] `GET /admin/gift-requests` — filter by status, join `User` để lấy email, sort DESC, hydrate gift_code string cho approved items.
  - [x] `POST /admin/gift-requests/{request_id}/approve` — lock + validate + mint via `_mint_gift_code` + link + commit.
  - [x] `POST /admin/gift-requests/{request_id}/reject` — lock + update status + commit.
  - [x] Guard: `admin: User = Depends(current_superuser)` trên cả 3 endpoints.

- [x] Import cần thiết (AC: 6)
  - [x] Thêm `GiftCode`, `GiftRequest`, `GiftRequestStatus` vào `from app.db import (` trong `admin_routes.py`.
  - [x] Thêm `_mint_gift_code` từ `app.routes.stripe_routes`.
  - [x] Thêm `GiftRequestApproveResponse`, `GiftRequestItem`, `GiftRequestListResponse`, `GiftRequestRejectRequest` từ `app.schemas.stripe`.

- [x] Verify
  - [x] `uv run pytest tests/unit/ -q --ignore=tests/unit/connectors/test_dexscreener_connector.py --ignore=tests/unit/indexing_pipeline/` → **408 passed**, 1 pre-existing dexscreener error (không liên quan).
  - [x] Manual end-to-end: seed `gift_request` (pending, max_monthly, 12 months) → GET /admin/gift-requests → 200 OK với item → POST approve → `GiftCode` được mint, `gift_requests.status=APPROVED`, `gift_code_id` được set → backend log xác nhận.

## Dev Notes

### Dependency

- Story 6.1 (migration 132 — bảng `gift_requests`, `gift_codes`).
- Story 6.2 (`GIFT_PRICING` config).
- Story 6.3 (`_generate_gift_code`, `_fulfill_gift_purchase` pattern).
- Story 6.5 (`GiftRequest` tạo khi user bấm fallback request).

### Pattern: Helper `_mint_gift_code`

Tách từ `_fulfill_gift_purchase` (stripe_routes.py:317). Signature đề xuất:

```python
async def _mint_gift_code(
    db_session: AsyncSession,
    *,
    plan_id: str,
    duration_months: int,
    amount_paid: int,
    purchaser_id: uuid.UUID,
    stripe_payment_intent_id: str | None = None,
) -> GiftCode:
    """Mint a new GiftCode with unique code (retry up to 3 times on collision).

    Caller must commit the session. Raises RuntimeError after max_attempts
    if collision persists — caller decides whether to rollback or propagate.
    """
    expires_at = datetime.now(UTC) + timedelta(days=365)
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        code = _generate_gift_code()
        gift = GiftCode(
            code=code,
            plan_id=plan_id,
            duration_months=duration_months,
            amount_paid=amount_paid,
            purchaser_id=purchaser_id,
            stripe_payment_intent_id=stripe_payment_intent_id,
            status=GiftCodeStatus.ACTIVE,
            expires_at=expires_at,
        )
        db_session.add(gift)
        try:
            await db_session.flush()
            return gift
        except IntegrityError:
            await db_session.rollback()
            if attempt == max_attempts:
                raise
    raise RuntimeError("unreachable")
```

**Note:** Refactor `_fulfill_gift_purchase` để sử dụng helper này (giữ behavior identical). Đảm bảo commit path trong webhook vẫn hoạt động.

### Pattern: Approve endpoint (mirror `approve_subscription_request`)

```python
@router.post(
    "/gift-requests/{request_id}/approve",
    response_model=GiftRequestApproveResponse,
)
async def approve_gift_request(
    request_id: uuid.UUID,
    admin: User = Depends(current_superuser),
    db_session: AsyncSession = Depends(get_async_session),
) -> GiftRequestApproveResponse:
    result = await db_session.execute(
        select(GiftRequest)
        .where(GiftRequest.id == request_id)
        .with_for_update()
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(404, "Gift request not found.")
    if req.status != GiftRequestStatus.PENDING:
        raise HTTPException(409, f"Request is already {req.status.value}.")

    plan_pricing = config.GIFT_PRICING.get(req.plan_id)
    if not plan_pricing or req.duration_months not in plan_pricing:
        raise HTTPException(
            400,
            f"Invalid plan_id/duration in request: {req.plan_id}/{req.duration_months}",
        )
    amount_paid = plan_pricing[req.duration_months]

    gift = await _mint_gift_code(
        db_session,
        plan_id=req.plan_id,
        duration_months=req.duration_months,
        amount_paid=amount_paid,
        purchaser_id=req.user_id,
        stripe_payment_intent_id=None,
    )

    req.status = GiftRequestStatus.APPROVED
    req.gift_code_id = gift.id
    req.updated_at = datetime.now(UTC)

    await db_session.commit()
    await db_session.refresh(gift)

    return GiftRequestApproveResponse(
        request_id=req.id,
        gift_code_id=gift.id,
        gift_code=gift.code,
        plan_id=gift.plan_id,
        duration_months=gift.duration_months,
    )
```

### Pattern: List endpoint

Join `User` để lấy email:

```python
@router.get("/gift-requests", response_model=GiftRequestListResponse)
async def list_gift_requests(
    status: str = "pending",
    admin: User = Depends(current_superuser),
    db_session: AsyncSession = Depends(get_async_session),
) -> GiftRequestListResponse:
    allowed = {"pending", "approved", "rejected", "all"}
    if status not in allowed:
        raise HTTPException(400, f"status must be one of {allowed}")

    query = select(GiftRequest, User.email).join(User, User.id == GiftRequest.user_id)
    if status != "all":
        query = query.where(GiftRequest.status == GiftRequestStatus(status))
    query = query.order_by(GiftRequest.created_at.desc())

    rows = (await db_session.execute(query)).all()
    items = [
        GiftRequestItem(
            id=r.GiftRequest.id,
            user_id=r.GiftRequest.user_id,
            user_email=r.email,
            plan_id=r.GiftRequest.plan_id,
            duration_months=r.GiftRequest.duration_months,
            status=r.GiftRequest.status.value,
            gift_code_id=r.GiftRequest.gift_code_id,
            gift_code=None,
            created_at=r.GiftRequest.created_at,
            updated_at=r.GiftRequest.updated_at,
        )
        for r in rows
    ]
    approved_code_ids = [i.gift_code_id for i in items if i.gift_code_id]
    if approved_code_ids:
        code_rows = await db_session.execute(
            select(GiftCode.id, GiftCode.code).where(GiftCode.id.in_(approved_code_ids))
        )
        code_map = {row.id: row.code for row in code_rows}
        items = [
            i.model_copy(update={"gift_code": code_map.get(i.gift_code_id)})
            for i in items
        ]
    return GiftRequestListResponse(items=items, count=len(items))
```

### Files cần thay đổi

1. `nowing_backend/app/schemas/stripe.py` — thêm 4 schema mới.
2. `nowing_backend/app/routes/stripe_routes.py` — extract `_mint_gift_code`.
3. `nowing_backend/app/routes/admin_routes.py` — thêm 3 endpoints + imports.

### Out of Scope

- Frontend UI (đẩy sang Story 6.9).
- Audit log separate table (defer — log sufficient).
- REJECTED resubmission cooldown (defer).
- Email notification khi approved/rejected (defer — admin copy-paste gift code thủ công cho user).

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- `uv run pytest tests/unit/ -q --ignore=...dexscreener... --ignore=...indexing_pipeline/` → **408 passed**, 1 error (pre-existing dexscreener unrelated). No regression.
- Enum case bug fix: `GiftRequestStatus(status.upper())` → `GiftRequestStatus(status)` (enum values lowercase: "pending", "approved", "rejected").
- Manual seed test: inserted `gift_request` via `docker exec psql` → GET 200 OK với item → POST approve → `GiftCode` được mint, `gift_requests.status=APPROVED`.

### Completion Notes List

- Thêm 4 Pydantic schemas vào `app/schemas/stripe.py`: `GiftRequestItem`, `GiftRequestListResponse`, `GiftRequestApproveResponse`, `GiftRequestRejectRequest`.
- Thêm `_mint_gift_code` helper tại `stripe_routes.py:317` (trước `_fulfill_gift_purchase`): dùng `flush()`, retry 3 lần on code collision, export để `admin_routes.py` import. `_fulfill_gift_purchase` giữ inline loop riêng vì error-handling khác cho Stripe webhook (log-and-return-200 thay vì raise).
- Thêm 3 endpoints vào `admin_routes.py`: `GET /admin/gift-requests`, `POST /admin/gift-requests/{id}/approve`, `POST /admin/gift-requests/{id}/reject`. Tất cả guard bởi `current_superuser`.
- Fixed enum case bug: `GiftRequestStatus(status)` thay vì `.upper()` (enum values là lowercase).
- `GiftCodeStatus` không cần import trực tiếp vào `admin_routes.py` — chỉ dùng bên trong `_mint_gift_code` trong `stripe_routes.py`.

### File List

- `nowing_backend/app/schemas/stripe.py` (modified — thêm `GiftRequestItem`, `GiftRequestListResponse`, `GiftRequestApproveResponse`, `GiftRequestRejectRequest`)
- `nowing_backend/app/routes/stripe_routes.py` (modified — thêm `_mint_gift_code` helper)
- `nowing_backend/app/routes/admin_routes.py` (modified — thêm imports + 3 gift request endpoints)

### Change Log

- 2026-04-17: Story 6.8 implemented — 4 schemas, `_mint_gift_code` helper, 3 admin endpoints (list/approve/reject gift requests), tests 408 passed.

### Review Findings

_Three-layer adversarial review (Blind Hunter + Edge Case Hunter + Acceptance Auditor) on 2026-04-17. All 6 ACs Pass per auditor. 0 decision-needed, 5 patches queued, 5 deferred, 12 dismissed._

- [x] [Review][Patch] `_mint_gift_code` calls `db_session.rollback()` on collision → hủy outer `SELECT FOR UPDATE` lock → double-mint race khi approve song song. Dùng SAVEPOINT (`begin_nested()`) thay raw rollback. [`nowing_backend/app/routes/stripe_routes.py:352-370`]
- [x] [Review][Patch] Constraint-name substring match quá rộng — `"code" in constraint_name and "pkey" not in constraint_name` match cả `gift_code_id` FK và future indexes chứa "code". Check exact `uq_gift_codes_code`. [`nowing_backend/app/routes/stripe_routes.py:353-360`]
- [x] [Review][Patch] Admin action + reject reason không được log — spec out-of-scope nói "log sufficient" nhưng `approve_gift_request`/`reject_gift_request` không có `logger.info(...)`. `body.reason` nhận vào rồi drop im lặng. Thêm log với `admin.id`, `request_id`, và reason. [`nowing_backend/app/routes/admin_routes.py:287-391`]
- [x] [Review][Patch] Param `status: str = "pending"` trong `list_gift_requests` shadow `from fastapi import status` — latent trap nếu code trong hàm sau này dùng `status.HTTP_*` sẽ AttributeError. Rename thành `status_filter`. [`nowing_backend/app/routes/admin_routes.py:234-248`]
- [x] [Review][Patch] `list_gift_requests` không có `limit`/`offset` — unbounded query, OOM risk ở scale. Thêm pagination mirror `get_gift_codes` (default 50, max 200). [`nowing_backend/app/routes/admin_routes.py:232-280`]

- [x] [Review][Defer] `admin_routes` coupling trực tiếp với private helper `_mint_gift_code` trong `stripe_routes` — design smell, không phải cycle hiện tại. Refactor helper ra `app/services/gift_codes.py` sau. [`nowing_backend/app/routes/admin_routes.py:24`] — deferred, refactor
- [x] [Review][Defer] Orphan `gift_code_id` serialize silent thành `gift_code=None` nếu `GiftCode` bị xóa — admin không thấy data corruption. Thêm warning/sentinel. [`nowing_backend/app/routes/admin_routes.py:261-280`] — deferred, admin UX
- [x] [Review][Defer] `expires_at` cố định 365 ngày từ approve time — không override được cho trường hợp admin phê duyệt trễ. Thêm optional param ở endpoint. [`nowing_backend/app/routes/admin_routes.py:317-325`] — deferred, admin flexibility
- [x] [Review][Defer] Không check `locked_user.is_active` trong approve — mint code cho user deactivated → không redeem được. [`nowing_backend/app/routes/admin_routes.py:287-341`] — deferred, minor UX
- [x] [Review][Defer] `GiftRequestItem.status: str` + `GiftCodeItem.status: str` — thiếu type safety, client không có contract enum. Đổi thành `Literal["pending", "approved", "rejected"]`. [`nowing_backend/app/schemas/stripe.py:107-117`] — deferred, schema tightening

**Dismissed (for transparency):**
- 8 findings ngoài scope Story 6.8 (thuộc stories 6.3/6.4/6.7): silent-swallow `_fulfill_gift_purchase`, self-gift redeem check, TOCTOU plan state, redeem không mark status, VI-only error messages, `30*duration_months` days, no rate-limit redeem, idempotency transient duplicates.
- `GiftRequestStatus(status)` `ValueError` — allowlist `_GIFT_STATUS_FILTERS` đã chặn invalid inputs trước khi gọi enum constructor.
- Reject email fallback `"<deleted>"` — intentional defensive pattern, tương tự `approve_subscription_request`.
- Reject body=None empty-request 422 — FastAPI behavior; frontend luôn gửi JSON body, không thực tế.
- Diff truncation artifact từ Blind Hunter — không phải bug thật.
