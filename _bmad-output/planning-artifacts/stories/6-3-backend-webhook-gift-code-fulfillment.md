# Story 6.3: Backend Webhook — Fulfillment Gift Code sau Payment

Status: done

## Story

As a Kỹ sư Hệ thống,
I want webhook handler tự động tạo gift code sau khi Stripe xác nhận thanh toán gift thành công,
So that purchaser nhận được code ngay lập tức mà không cần can thiệp thủ công từ admin.

## Acceptance Criteria

1. Khi Stripe gửi `checkout.session.completed` với `metadata.purchase_type == "gift"`, hàm `_fulfill_gift_purchase()` được gọi.
2. `_fulfill_gift_purchase()` generate code format `GIFT-XXXX-XXXX-XXXX` bằng `secrets.choice(string.ascii_uppercase + string.digits)` (12 random chars chia thành 3 nhóm 4).
3. Tạo record trong bảng `gift_codes` với: `code` (generated), `plan_id` (từ metadata), `duration_months` (từ metadata), `amount_paid` (từ metadata), `purchaser_id` (từ metadata), `stripe_payment_intent_id` (từ checkout session), `status='active'`, `expires_at = now() + 1 year`.
4. Nếu insert bị lỗi unique constraint (code collision) → retry tối đa 3 lần với code mới trước khi log error và return (không throw, không fail Stripe webhook).
5. Webhook trả về `StripeWebhookResponse()` kể cả khi DB lỗi — không bao giờ trả về non-200 cho Stripe (idempotency).
6. Các webhook branch khác (`"subscription"`, `"token_topup"`) vẫn hoạt động bình thường — không bị ảnh hưởng.
7. `import secrets` và `import string` được thêm vào `stripe_routes.py`.
8. `GiftCode` và `GiftCodeStatus` được import từ `app.db` vào `stripe_routes.py`.

## Tasks / Subtasks

- [x] Thêm `import secrets, string` vào `stripe_routes.py` (AC: 2, 7)
  - [x] Thêm vào block imports (line ~5–9), cạnh `import uuid`

- [x] Thêm `GiftCode`, `GiftCodeStatus` vào `from app.db import (` block (AC: 8)
  - [x] Line ~17–22 trong `stripe_routes.py`

- [x] Thêm helper `_generate_gift_code()` vào `stripe_routes.py` (AC: 2)
  - [x] Đặt cạnh các helper khác (sau `_get_metadata` hoặc sau `_fulfill_token_topup`)
  - [x] Returns string format `GIFT-XXXX-XXXX-XXXX`

- [x] Thêm `_fulfill_gift_purchase()` vào `stripe_routes.py` (AC: 1–5)
  - [x] Đặt SAU `_fulfill_token_topup()` (~line 267), TRƯỚC subscription helpers
  - [x] Extract metadata: `purchaser_id`, `plan_id`, `duration_months`, `amount_cents` từ `checkout_session`
  - [x] Retry loop tối đa 3 lần khi unique constraint collision
  - [x] Set `expires_at = datetime.now(UTC) + timedelta(days=365)`
  - [x] Log success và lỗi rõ ràng
  - [x] Luôn trả về `StripeWebhookResponse()` — không raise exception

- [x] Cập nhật webhook handler để gọi `_fulfill_gift_purchase()` (AC: 1, 6)
  - [x] Trong block `metadata.get("purchase_type")` (~line 870), thêm branch `"gift"` TRƯỚC `"token_packs"/"token_topup"`
  - [x] Pattern: `if metadata.get("purchase_type") == "gift": return await _fulfill_gift_purchase(db_session, checkout_session)`

- [x] Verify
  - [x] `uv run pytest tests/unit/ -q --ignore=tests/unit/connectors/test_dexscreener_connector.py --ignore=tests/unit/indexing_pipeline/` → **408 passed** (1 pre-existing dexscreener error không liên quan)

## Dev Notes

### Dependency: Story 6.1

Migration 132 (bảng `gift_codes`) phải đã được chạy trước khi story này được deploy. `GiftCode` model phải có trong `app.db`.

### Pattern cho `_generate_gift_code()` — PHẢI tuân thủ

```python
import secrets
import string

_GIFT_CODE_CHARS = string.ascii_uppercase + string.digits


def _generate_gift_code() -> str:
    """Generate a random gift code in format GIFT-XXXX-XXXX-XXXX."""
    groups = ["".join(secrets.choice(_GIFT_CODE_CHARS) for _ in range(4)) for _ in range(3)]
    return "GIFT-" + "-".join(groups)
```

### Pattern cho `_fulfill_gift_purchase()` — PHẢI tuân thủ

```python
async def _fulfill_gift_purchase(
    db_session: AsyncSession, checkout_session: Any
) -> StripeWebhookResponse:
    """Create a gift code record after a confirmed Stripe gift payment.

    Idempotency note: if the DB insert fails, we log the error and return
    a successful response to Stripe to prevent webhook retries from creating
    duplicate charges.
    """
    from sqlalchemy.exc import IntegrityError

    metadata = _get_metadata(checkout_session)
    purchaser_id_str = metadata.get("purchaser_id")
    plan_id = metadata.get("plan_id")
    duration_months_str = metadata.get("duration_months")
    amount_cents_str = metadata.get("amount_cents")

    if not all([purchaser_id_str, plan_id, duration_months_str, amount_cents_str]):
        logger.warning(
            "Gift webhook missing metadata for session %s: %s",
            checkout_session.id,
            metadata,
        )
        return StripeWebhookResponse()

    try:
        purchaser_id = uuid.UUID(purchaser_id_str)
        duration_months = int(duration_months_str)
        amount_paid = int(amount_cents_str)
    except (ValueError, TypeError) as exc:
        logger.error(
            "Gift webhook invalid metadata for session %s: %s",
            checkout_session.id,
            exc,
        )
        return StripeWebhookResponse()

    payment_intent_id = str(getattr(checkout_session, "payment_intent", "") or "")
    expires_at = datetime.now(UTC) + timedelta(days=365)

    # Retry loop for unique constraint collision (extremely rare)
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        code = _generate_gift_code()
        gift = GiftCode(
            code=code,
            plan_id=plan_id,
            duration_months=duration_months,
            amount_paid=amount_paid,
            purchaser_id=purchaser_id,
            stripe_payment_intent_id=payment_intent_id or None,
            status=GiftCodeStatus.ACTIVE,
            expires_at=expires_at,
        )
        db_session.add(gift)
        try:
            await db_session.commit()
            logger.info(
                "Gift code %s created for user %s (session %s)",
                code,
                purchaser_id,
                checkout_session.id,
            )
            return StripeWebhookResponse()
        except IntegrityError:
            await db_session.rollback()
            if attempt < max_attempts:
                logger.warning(
                    "Gift code collision on attempt %d for session %s, retrying",
                    attempt,
                    checkout_session.id,
                )
            else:
                logger.error(
                    "Failed to create gift code after %d attempts for session %s",
                    max_attempts,
                    checkout_session.id,
                )
                return StripeWebhookResponse()

    return StripeWebhookResponse()
```

### Cập nhật webhook handler (~line 870) — chính xác đoạn cần sửa

Đoạn hiện tại:
```python
metadata = _get_metadata(checkout_session)
if metadata.get("purchase_type") in {"token_packs", "token_topup"}:
    return await _fulfill_token_topup(db_session, checkout_session)

logger.warning(
    "Unrecognized payment-mode checkout session %s with purchase_type=%s",
    ...
)
return StripeWebhookResponse()
```

Cần thay thành:
```python
metadata = _get_metadata(checkout_session)
if metadata.get("purchase_type") == "gift":
    return await _fulfill_gift_purchase(db_session, checkout_session)
if metadata.get("purchase_type") in {"token_packs", "token_topup"}:
    return await _fulfill_token_topup(db_session, checkout_session)

logger.warning(...)
return StripeWebhookResponse()
```

### Import `GiftCode`, `GiftCodeStatus` từ `app.db`

Cập nhật block `from app.db import (` (hiện tại line 17–22):

```python
from app.db import (
    GiftCode,              # NEW
    GiftCodeStatus,        # NEW
    SubscriptionRequest,
    SubscriptionRequestStatus,
    SubscriptionStatus,
    User,
    get_async_session,
)
```

### `_get_metadata` helper hiện có

`stripe_routes.py` đã có `_get_metadata(checkout_session)` trả về `dict[str, str]`. Dùng trực tiếp — không cần thêm helper mới.

### IntegrityError import

`from sqlalchemy.exc import IntegrityError` — import cục bộ bên trong function để tránh pollute module-level imports (pattern quen thuộc trong Django/FastAPI projects). Hoặc thêm vào top-level imports nếu muốn nhất quán với style hiện tại.

### Không cần notification email trong story này

AC gốc đề cập "code được đính kèm vào response email" — nhưng Nowing chưa có email service. Story này chỉ lưu code vào DB. Frontend (Story 6.6) sẽ fetch và hiển thị code cho purchaser. Email có thể là enhancement sau.

### success_url không embed code

Gift code được lưu DB, không embed vào redirect URL (security risk). Frontend Story 6.6 sẽ gọi `GET /api/v1/stripe/gift-codes` để lấy code sau khi redirect về purchase-success page.

### Verification command

```bash
cd nowing_backend
uv run pytest tests/unit/ -q \
  --ignore=tests/unit/connectors/test_dexscreener_connector.py \
  --ignore=tests/unit/indexing_pipeline/
```

### Project Structure Notes

- Chỉ sửa một file: `nowing_backend/app/routes/stripe_routes.py`
  - Thêm `import secrets, string` (top)
  - Thêm `GiftCode, GiftCodeStatus` vào `from app.db import`
  - Thêm `_GIFT_CODE_CHARS` constant
  - Thêm `_generate_gift_code()` helper
  - Thêm `_fulfill_gift_purchase()` function
  - Update webhook dispatch block

### References

- [Source: nowing_backend/app/routes/stripe_routes.py#184-267] — `_fulfill_token_topup` pattern (idempotency, SELECT FOR UPDATE, logging)
- [Source: nowing_backend/app/routes/stripe_routes.py#840-885] — webhook dispatch block (cần sửa)
- [Source: nowing_backend/app/routes/stripe_routes.py#17-22] — `from app.db import` block
- [Source: nowing_backend/app/db.py#GiftCode] — model schema (từ story 6.1)
- [Source: _bmad-output/planning-artifacts/epics.md#Story-6.3] — AC gốc từ Epic

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Debug Log References

- pytest tests/unit/ → 408 passed, 1 pre-existing dexscreener error (không liên quan)

### Completion Notes List

- `import secrets, string` + `from sqlalchemy.exc import IntegrityError` được thêm ở top-level (nhất quán với style hiện tại của file, không dùng lazy import)
- `GiftCode, GiftCodeStatus` được thêm vào `from app.db import (` block (alphabetical order)
- `_GIFT_CODE_CHARS = string.ascii_uppercase + string.digits` module-level constant
- `_generate_gift_code()` dùng `secrets.choice` (cryptographic random) — format `GIFT-XXXX-XXXX-XXXX` (19 chars)
- `_fulfill_gift_purchase()` đặt giữa `_fulfill_token_topup` và `# Subscription event helpers` section, với comment header riêng
- Retry loop tối đa 3 lần trên `IntegrityError` — luôn trả `StripeWebhookResponse()` kể cả khi retry exhausted (idempotency yêu cầu webhook không bao giờ non-200)
- Metadata validation: thiếu field → warning log + return 200; invalid type → error log + return 200
- Webhook dispatch: branch `"gift"` được đặt TRƯỚC `"token_packs"/"token_topup"` theo spec

### 🔧 Fix cross-story: column `code` VARCHAR(16) → VARCHAR(32)

Story 6.1 migration 132 set `code = Column(String(16))`, nhưng Story 6.3 spec format `GIFT-XXXX-XXXX-XXXX` = **19 chars** → sẽ gây `StringDataRightTruncation` khi commit. Fix:
- Tạo **migration 133** `ALTER COLUMN code TYPE VARCHAR(32)` (non-destructive, idempotent)
- Update `GiftCode.code = Column(String(32))` trong `app/db.py`
- Downgrade path trả về `VARCHAR(16)` (sẽ fail nếu có rows >16 chars, như note trong downgrade docstring)

### File List

- `nowing_backend/app/routes/stripe_routes.py` (modified — thêm imports `secrets`/`string`/`IntegrityError`/`GiftCode`/`GiftCodeStatus`, `_GIFT_CODE_CHARS` constant, `_generate_gift_code` helper, `_fulfill_gift_purchase` function, update webhook dispatch)
- `nowing_backend/app/db.py` (modified — `GiftCode.code` `String(16)` → `String(32)` để fit format `GIFT-XXXX-XXXX-XXXX`)
- `nowing_backend/alembic/versions/133_widen_gift_codes_code_column.py` (new — ALTER COLUMN `gift_codes.code` từ VARCHAR(16) → VARCHAR(32))

## Review Findings (2026-04-17)

Multi-layer adversarial review via 3 subagents (Blind Hunter, Edge Case Hunter, Acceptance Auditor). Findings triaged into patched / deferred / dismissed.

### Patched in this story

- **P1 — Gift code leaked in INFO log (Critical)** — `logger.info("Gift code %s created...", code, ...)` wrote the full redeemable bearer credential to logs. Fixed via `_mask_gift_code()` returning `GIFT-****-****-XXXX` (last 4 only). Reason: logs are shipped to multiple sinks (Loki/CloudWatch/dev consoles) and any leak compromises all outstanding unredeemed gifts.
- **P2 — Webhook idempotency gap (Critical)** — Stripe redeliveries reuse `payment_intent_id` but may surface with a different `session.id`. Without a pre-check, every retry hit the `uq_gift_codes_stripe_payment_intent_id` partial unique index and burned all 3 code-collision retries silently. Fixed via `SELECT 1 FROM gift_codes WHERE stripe_payment_intent_id = :pi` before insert (same pattern as `_fulfill_token_topup` using `fulfilled_topup_sessions`).
- **P3 — Broad `except IntegrityError` (High)** — Retry loop retried on FK violations / payment_intent unique collisions (non-recoverable failures), wasting attempts. Fixed by inspecting `exc.orig.diag.constraint_name` — only retries when the failing constraint references `code`; all other integrity errors log + return immediately.
- **P4 — Metadata values not cross-verified (High)** — `amount_cents` and `plan_id` from Stripe metadata were trusted blindly. Fixed by cross-checking against `config.GIFT_PRICING[plan_id][duration_months]` inside the webhook handler (defense-in-depth — even though metadata is signed by Stripe, the pricing table is the source of truth). Also added `duration_months > 0` and `amount_paid > 0` guards.
- **P5 — Misleading docstring (Medium)** — Original said "if the DB insert fails" but the handler only caught `IntegrityError`. Rewrote docstring to accurately describe all failure paths and the manual-reconciliation expectation.
- **P6 — Migration 133 downgrade data loss (Medium)** — `downgrade()` silently narrowed `VARCHAR(32) → VARCHAR(16)` which truncates/rejects any real 19-char gift codes. Replaced with `raise NotImplementedError(...)` and explanatory message. Reason: data integrity > automation convenience.
- **P7 — Unreachable trailing `return` (Nit)** — Removed the unreachable `return StripeWebhookResponse()` after the retry loop; every path inside the loop now returns.
- **P8 — `payment_intent` attribute unwrap (Medium)** — `str(getattr(..., "payment_intent", "") or "")` stringifies a PaymentIntent object as `"<PaymentIntent at 0x...>"` if Stripe returns the expanded object. Fixed by unwrapping `.id` when the attribute has one.

### Deferred (tracked in `deferred-work.md`)

- Admin alerting when webhook returns 200 with manual-reconciliation error (currently only logs).
- Unit tests for `_fulfill_gift_purchase` happy path + all failure branches (no tests exist for this module yet).
- Extract shared Stripe webhook idempotency helper (pattern now duplicated across `_fulfill_token_topup` and `_fulfill_gift_purchase`).

### Dismissed

- Entropy of `secrets.choice(ascii_uppercase + digits)` — 36^12 ≈ 4.7e18; collision risk negligible at any realistic scale.
- `expires_at = now + 365 days` uses webhook-receipt time (not payment time). Webhook delay is bounded at minutes; intentional trade-off.
- Out-of-spec migration 133 + `db.py` edit — flagged by Acceptance Auditor as violating "only edit one file" rule in spec, but the cross-story schema bug (VARCHAR(16) cannot fit 19-char codes) would have caused runtime failure. Accepted as a necessary pre-deploy fix; documented in Dev Agent Record § "Fix cross-story".

### Verification

`uv run pytest tests/unit/ -q --ignore=tests/unit/connectors/test_dexscreener_connector.py --ignore=tests/unit/indexing_pipeline/` → **408 passed** (1 pre-existing dexscreener error unrelated).
