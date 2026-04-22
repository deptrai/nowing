# Story 6.1: Database Migration — Bảng Gift Codes & Gift Requests

Status: done

## Story

As a Kỹ sư Hệ thống,
I want tạo migration Alembic số 132 để thêm bảng `gift_codes` và `gift_requests` vào Postgres,
so that hệ thống có đủ cấu trúc dữ liệu để lưu trữ gift code và luồng admin-approval fallback mà không ảnh hưởng các bảng hiện có.

## Acceptance Criteria

1. `alembic upgrade head` tạo thành công bảng `gift_codes` với các cột: `id UUID PK`, `code VARCHAR(16) UNIQUE NOT NULL`, `plan_id VARCHAR(50) NOT NULL`, `duration_months INTEGER NOT NULL`, `amount_paid INTEGER NOT NULL` (cents), `purchaser_id UUID FK user.id CASCADE`, `stripe_payment_intent_id VARCHAR(255)`, `redeemer_id UUID FK user.id SET NULL nullable`, `status VARCHAR(20) DEFAULT 'active' NOT NULL`, `expires_at TIMESTAMP WITH TIME ZONE NOT NULL`, `created_at TIMESTAMP WITH TIME ZONE server_default=now()`, `redeemed_at TIMESTAMP WITH TIME ZONE nullable`.
2. `alembic upgrade head` tạo thành công bảng `gift_requests` với các cột: `id UUID PK`, `user_id UUID FK user.id CASCADE NOT NULL`, `plan_id VARCHAR(50) NOT NULL`, `duration_months INTEGER NOT NULL`, `status VARCHAR(20) DEFAULT 'pending' NOT NULL`, `gift_code_id UUID FK gift_codes.id SET NULL nullable`, `created_at TIMESTAMP WITH TIME ZONE server_default=now()`, `updated_at TIMESTAMP WITH TIME ZONE nullable`.
3. Downgrade migration hoạt động sạch — drop `gift_requests` trước (FK dependency), sau đó drop `gift_codes`.
4. Không có thay đổi nào đến bảng `user`, `subscription_requests`, hay bảng nào khác hiện có.
5. Model Python `GiftCode` và `GiftCodeStatus` enum, `GiftRequest` và `GiftRequestStatus` enum được thêm vào `nowing_backend/app/db.py`, tuân thủ đúng pattern hiện tại.

## Tasks / Subtasks

- [x] Thêm enums và models vào `db.py` (AC: 5)
  - [x] Thêm `GiftCodeStatus(StrEnum)` với values: `active`, `redeemed`, `expired`, `cancelled`
  - [x] Thêm `GiftCode(Base, TimestampMixin)` class — `__tablename__ = "gift_codes"`, `__allow_unmapped__ = True`
  - [x] Thêm `GiftRequestStatus(StrEnum)` với values: `pending`, `approved`, `rejected`
  - [x] Thêm `GiftRequest(Base)` class — `__tablename__ = "gift_requests"`, `__allow_unmapped__ = True`
  - [x] Đặt classes SAU `SubscriptionRequest` (line ~1730) và TRƯỚC `User` class (line ~1917)
- [x] Tạo Alembic migration file (AC: 1, 2, 3, 4)
  - [x] File: `nowing_backend/alembic/versions/132_add_gift_codes_tables.py`
  - [x] `revision = "132"`, `down_revision = "131"` (current head)
  - [x] `upgrade()`: create `gift_codes` table, then `gift_requests` table (FK order)
  - [x] `downgrade()`: drop `gift_requests` first, then `gift_codes`
  - [x] Dùng `gen_random_uuid()` cho PKs, `now()` cho timestamps
- [x] Verify migration chạy sạch
  - [x] `cd nowing_backend && uv run alembic upgrade head` — không lỗi
  - [x] `uv run alembic downgrade -1` — drop sạch
  - [x] `uv run alembic upgrade head` lại — idempotent

## Dev Notes

### Pattern hiện tại trong `db.py` — PHẢI tuân thủ

**Vị trí thêm code:** Sau `SubscriptionRequest` class (~line 1730), trước `User` class (~line 1917).

**Pattern cho model sử dụng `Base` trực tiếp** (không FK phức tạp qua fastapi-users):
```python
class GiftCodeStatus(StrEnum):
    ACTIVE = "active"
    REDEEMED = "redeemed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class GiftCode(Base, TimestampMixin):
    """Stores gift codes purchased via Stripe one-time payment."""

    __tablename__ = "gift_codes"
    __allow_unmapped__ = True

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    code = Column(String(16), unique=True, nullable=False, index=True)
    plan_id = Column(String(50), nullable=False)
    duration_months = Column(Integer, nullable=False)
    amount_paid = Column(Integer, nullable=False)  # in cents
    purchaser_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_payment_intent_id = Column(String(255), nullable=True)
    redeemer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(
        SQLAlchemyEnum(
            GiftCodeStatus,
            name="giftcodestatus",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=GiftCodeStatus.ACTIVE,
        server_default="active",
    )
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    redeemed_at = Column(TIMESTAMP(timezone=True), nullable=True)
```

**Pattern TimestampMixin** (từ line ~539):
```python
class TimestampMixin:
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=True, onupdate=text("now()"))
```
→ `GiftCode` extends `TimestampMixin` → tự có `created_at`, `updated_at`.  
→ `GiftRequest` extends `Base` only (không cần `updated_at` auto) → define `created_at` và `updated_at` manually như `SubscriptionRequest` pattern.

**SQLAlchemy Enum với `create_type=False`:** Xem cách `SubscriptionRequest` define enum — phải dùng `values_callable=lambda x: [e.value for e in x]` và `create_type=False` vì enum type được tạo thủ công trong migration.

### Pattern cho Alembic migration — PHẢI theo

Xem `130_add_purchased_tokens.py` và `127_add_subscription_requests_table.py` làm template:

```python
"""132_add_gift_codes_tables

Revision ID: 132
Revises: 131
Create Date: 2026-04-16

Adds gift_codes and gift_requests tables for Gift Subscription feature (Epic 6).
"""

from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "132"
down_revision: str | None = "131"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create enums first
    op.execute("CREATE TYPE giftcodestatus AS ENUM ('active', 'redeemed', 'expired', 'cancelled')")
    op.execute("CREATE TYPE giftrequeststatus AS ENUM ('pending', 'approved', 'rejected')")

    op.create_table(
        "gift_codes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("plan_id", sa.String(50), nullable=False),
        sa.Column("duration_months", sa.Integer(), nullable=False),
        sa.Column("amount_paid", sa.Integer(), nullable=False),
        sa.Column("purchaser_id", sa.UUID(), nullable=False),
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
        sa.Column("redeemer_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Enum("active", "redeemed", "expired", "cancelled", name="giftcodestatus", create_type=False), server_default="active", nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["purchaser_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["redeemer_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_gift_codes_code", "gift_codes", ["code"])
    op.create_index("ix_gift_codes_purchaser_id", "gift_codes", ["purchaser_id"])

    op.create_table(
        "gift_requests",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.String(50), nullable=False),
        sa.Column("duration_months", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("pending", "approved", "rejected", name="giftrequeststatus", create_type=False), server_default="pending", nullable=False),
        sa.Column("gift_code_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gift_code_id"], ["gift_codes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gift_requests_user_id", "gift_requests", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_gift_requests_user_id", "gift_requests")
    op.drop_table("gift_requests")
    op.drop_index("ix_gift_codes_purchaser_id", "gift_codes")
    op.drop_index("ix_gift_codes_code", "gift_codes")
    op.drop_table("gift_codes")
    op.execute("DROP TYPE IF EXISTS giftrequeststatus")
    op.execute("DROP TYPE IF EXISTS giftcodestatus")
```

### Hai User model variants — KHÔNG cần thay đổi

`db.py` có 2 `User` class (line ~1917 và ~2057) cho 2 chế độ deploy. Story này KHÔNG thay đổi `User` — chỉ thêm models mới.

### Import hiện có trong `db.py` — KHÔNG cần thêm

Các import cần thiết (`UUID`, `Column`, `String`, `Integer`, `ForeignKey`, `TIMESTAMP`, `text`, `SQLAlchemyEnum`, `StrEnum`, `Base`, `TimestampMixin`) đã có sẵn trong file. Chỉ thêm classes, không thêm import.

### Zero Publication — KHÔNG cần cập nhật

`gift_codes` và `gift_requests` là backend-only tables — không sync qua rocicorp/zero. Không cần thêm vào `zero_publication` (migration 116/117).

### Verification command
```bash
cd nowing_backend
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
uv run pytest tests/unit/ -q \
  --ignore=tests/unit/connectors/test_dexscreener_connector.py \
  --ignore=tests/unit/indexing_pipeline/
```

### Project Structure Notes

- Migration file: `nowing_backend/alembic/versions/132_add_gift_codes_tables.py`
- Model additions: `nowing_backend/app/db.py` (sau line ~1730, trước line ~1917)
- Không tạo file mới nào khác trong story này

### References

- [Source: nowing_backend/alembic/versions/130_add_purchased_tokens.py] — migration pattern
- [Source: nowing_backend/alembic/versions/127_add_subscription_requests_table.py] — create_table pattern với UUID, enums, FKs
- [Source: nowing_backend/app/db.py#1687-1740] — SubscriptionRequest pattern (Base + manual timestamps)
- [Source: nowing_backend/app/db.py#539-548] — TimestampMixin definition
- [Source: _bmad-output/planning-artifacts/epics.md#Story-6.1] — AC gốc từ Epic

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-7) — bmad-dev-story workflow, 2026-04-17.

### Debug Log References

- Lần đầu chạy `alembic upgrade head` báo `DuplicateObjectError: type "giftcodestatus" already exists` vì dùng `op.execute("CREATE TYPE ...")` cộng với `sa.Enum(..., create_type=False)` trong `op.create_table` → alembic/SQLAlchemy cố tạo lại enum khi xử lý column. Rewrote migration theo pattern của `115_add_page_purchases_table.py`: dùng `postgresql.ENUM(...).create(conn, checkfirst=True)` trước, kiểm tra `information_schema.tables` để bảo đảm idempotent, tất cả index dùng `CREATE INDEX IF NOT EXISTS`. Upgrade → downgrade → upgrade đều pass clean.

### Completion Notes List

- Thêm `GiftCodeStatus`, `GiftCode`, `GiftRequestStatus`, `GiftRequest` vào `nowing_backend/app/db.py` đúng vị trí (sau `SubscriptionRequest`, trước `SearchSpaceRole`). `GiftCode` kế thừa `TimestampMixin` (có `created_at`), `GiftRequest` kế thừa `Base` với `created_at`/`updated_at` khai báo thủ công theo pattern của `SubscriptionRequest`. Không khai báo relationship `back_populates` trên `User` để bảo toàn AC4 (không đụng tới `User` model).
- Migration `132_add_gift_codes_tables.py` idempotent, có `CREATE INDEX IF NOT EXISTS` cho cả `ix_gift_codes_code`, `ix_gift_codes_purchaser_id`, `ix_gift_requests_user_id`. FK: `purchaser_id → user.id ON DELETE CASCADE`, `redeemer_id → user.id ON DELETE SET NULL`, `user_id → user.id ON DELETE CASCADE`, `gift_code_id → gift_codes.id ON DELETE SET NULL`. Unique constraint trên `gift_codes.code` tên `uq_gift_codes_code`.
- Verify schema qua `information_schema.columns` và `pg_constraint`: tất cả cột, kiểu, default (`gen_random_uuid()`, `now()`, `'active'::giftcodestatus`, `'pending'::giftrequeststatus`), nullability, và FK đều khớp AC1/AC2.
- `ruff check app/db.py alembic/versions/132_add_gift_codes_tables.py` → clean.
- `pytest tests/unit/ --ignore=tests/unit/connectors/test_dexscreener_connector.py --ignore=tests/unit/indexing_pipeline/` → 408 passed, 1 error pre-existing (`tests/unit/tasks/test_dexscreener_indexer.py` — SQLite test fixture không parse được cast PG-specific `'PENDING'::pagepurchasestatus` từ migration 115 — KHÔNG liên quan gift code changes).

### File List

- `nowing_backend/app/db.py` (modified — thêm `GiftCodeStatus`, `GiftCode`, `GiftRequestStatus`, `GiftRequest` vào giữa `SubscriptionRequest` và `SearchSpaceRole`; post-review: `unique=True` trên `stripe_payment_intent_id`, bỏ redundant `index=True` trên `code`)
- `nowing_backend/alembic/versions/132_add_gift_codes_tables.py` (new; post-review: bỏ redundant `ix_gift_codes_code`, thêm `ix_gift_codes_created_at`, partial unique index `uq_gift_codes_stripe_payment_intent_id WHERE NOT NULL`, downgrade `DROP TYPE ... CASCADE`)

### Review Findings

#### Patch (fix now)

- [x] [Review][Patch] Missing UNIQUE on `gift_codes.stripe_payment_intent_id` — webhook idempotency gap; retried Stripe webhook can create duplicate gift codes for one payment (mismatch với pattern `PagePurchase.stripe_checkout_session_id` có `unique=True`) [nowing_backend/app/db.py:~1755 · nowing_backend/alembic/versions/132_add_gift_codes_tables.py:71]
- [x] [Review][Patch] Downgrade `DROP TYPE` không dùng `CASCADE` — sẽ fail với "cannot drop type because other objects depend on it" nếu migration sau tham chiếu enum [nowing_backend/alembic/versions/132_add_gift_codes_tables.py:174-175]
- [x] [Review][Patch] Redundant `ix_gift_codes_code` — `UniqueConstraint("code")` đã tạo implicit btree index; `CREATE INDEX ix_gift_codes_code` tạo index trùng, lãng phí disk + ghi chậm hơn [nowing_backend/alembic/versions/132_add_gift_codes_tables.py:109-111 · nowing_backend/app/db.py:1753 (index=True)]
- [x] [Review][Patch] Thiếu `ix_gift_codes_created_at` — `TimestampMixin.created_at` khai báo `index=True`; migration 115 (pattern template) có `CREATE INDEX IF NOT EXISTS ix_page_purchases_created_at` tương ứng; migration 132 không có → ORM `create_all()` và Alembic-upgraded DB sẽ lệch nhau [nowing_backend/alembic/versions/132_add_gift_codes_tables.py:112-115]

#### Defer (pre-existing pattern / out of scope)

- [x] [Review][Defer] CHECK constraint `expires_at > created_at` — deferred, pre-existing (`SubscriptionRequest`, `PagePurchase` cũng không có defensive CHECK)
- [x] [Review][Defer] CHECK constraint `amount_paid >= 0` và `duration_months > 0` — deferred, pre-existing (`PagePurchase.amount_total` không có check)
- [x] [Review][Defer] `gift_requests.updated_at` không có `onupdate` trigger — deferred, app-level concern; fit project pattern (TimestampMixin không trigger)
- [x] [Review][Defer] Thiếu `currency` column trên `gift_codes` (so với `PagePurchase`) — deferred, không thuộc AC; USD-only launch
- [x] [Review][Defer] Thiếu `relationship()` back-ref trên `GiftCode`/`GiftRequest` → `User` — deferred, không thuộc AC; query code có thể explicit join
- [x] [Review][Defer] Thiếu composite index `ix_gift_requests_status_created_at` cho admin query hot path — deferred, revisit trong Story 6-5 khi query pattern rõ ràng

#### Dismissed (spec-mandated or false positive)

- AA/BH nhận định sai "gift_codes missing `updated_at`": AC1 KHÔNG liệt kê `updated_at`; `TimestampMixin` hiện tại chỉ cung cấp `created_at` (line 539–547), không phải cả hai. No drift.
- Enum pattern `create_type=False` + `.create(checkfirst=True)`: đúng idiom của migration 115 trong codebase; offline alembic mode không phải workflow được dùng.
- `code VARCHAR(16)`: spec AC1 mandate literal length.
- `purchaser_id` CASCADE, `redeemer_id` SET NULL: spec AC1 mandate.
- `GiftRequestStatus` chỉ có `pending/approved/rejected`: spec AC2 mandate.
- `__allow_unmapped__ = True`: project-wide pattern (khớp với `SubscriptionRequest`, `PagePurchase`).
- Gift code collision retry logic: application-level concern, không thuộc schema scope.
