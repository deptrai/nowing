---
baseline_commit: 1bd12a1d4
---

# Story 8.3: Usage & Credit Dashboard (New Gap)

**Status:** done  
**Epic:** 8 — Platform Operations  
**Source:** <ref_file file="/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/epics.md" />  
**Related PRD:** NFR-7 (§5) in <ref_file file="/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" />  
**Related Architecture:** AD-8, AD-10, AD-DEFER-5 in <ref_file file="/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />  

## Story

As a user,  
I want a dashboard showing my token usage and credit balance over time,  
So that I can understand costs and usage patterns.

## Acceptance Criteria

1. **Dashboard page accessible**
   - **Given** user đã xác thực và là member của workspace
   - **When** user mở `/dashboard/[workspace_id]/usage`
   - **Then** trang hiển thị:
     - current `credit_micros_balance` và `credit_micros_reserved`
     - total tokens và total cost theo workspace
     - breakdown theo `usage_type`, model, provider
     - lịch sử `CreditPurchase`, `PagePurchase`, `UserIncentiveTask`

2. **Backend aggregate API**
   - `GET /api/v1/usage/summary?workspace_id=<id>&start_date=...&end_date=...` trả về balance/reserved, workspace totals, breakdowns.
   - `GET /api/v1/usage/time-series?workspace_id=<id>&granularity=day` trả về time-series cost/tokens.
   - `GET /api/v1/usage/transactions` trả về unified transaction history (purchases + incentives).

3. **Permissions**
   - User phải là member của workspace mới được xem usage của workspace đó.
   - PAT không được phép (endpoint dùng `require_session_context` hoặc tương đương).

4. **Date range filtering**
   - User có thể chọn khoảng thời gian (7 ngày, 30 ngày, 90 ngày, custom range).
   - Mặc định là 30 ngày.

5. **Empty state**
   - Khi chưa có usage, dashboard hiển thị empty state thân thiện, balance vẫn hiển thị.

6. **Responsive layout**
   - Dashboard hiển thị tốt trên desktop và tablet.

7. **No schema changes required**
   - Tận dụng bảng `TokenUsage`, `CreditPurchase`, `PagePurchase`, `UserIncentiveTask`, `User` hiện có.
   - Nếu query chậm, mới cân nhắc thêm composite index `(workspace_id, created_at)` trên `token_usage`.

## Tasks / Subtasks

- [x] **Backend: usage routes, service, schemas** (AC 2, 3)
  - [x] Tạo `nowing_backend/app/schemas/usage.py` với `UsageSummaryResponse`, `UsageTimeSeriesResponse`, `UsageTransactionResponse`, `UsageBreakdownItem`.
  - [x] Tạo `nowing_backend/app/services/usage_service.py` với aggregation logic từ `TokenUsage`, `CreditPurchase`, `PagePurchase`, `UserIncentiveTask`.
  - [x] Tạo `nowing_backend/app/routes/usage_routes.py` với 3 endpoints.
  - [x] Đăng ký router trong `nowing_backend/app/routes/__init__.py`.
- [x] **Backend: permissions & edge cases** (AC 3)
  - [x] Dùng `check_workspace_access` để verify workspace membership.
  - [x] Validate `workspace_id` và date range.
  - [x] Handle `granularity` enum (`day`, `week`, `month`).
- [x] **Frontend: types và API service** (AC 1, 2)
  - [x] Tạo `nowing_web/contracts/types/usage.types.ts`.
  - [x] Tạo `nowing_web/lib/apis/usage-api.service.ts`.
- [x] **Frontend: dashboard page và components** (AC 1, 4, 5, 6)
  - [x] Tạo `nowing_web/app/dashboard/[workspace_id]/usage/page.tsx` và `usage-content.tsx`.
  - [x] Summary cards tích hợp trong `usage-content.tsx` (decided: không tách file `usage-summary-cards.tsx` riêng để giảm thiểu boilerplate).
  - [x] Tạo `nowing_web/components/usage/usage-chart.tsx` (dùng `recharts`).
  - [x] Tạo `nowing_web/components/usage/usage-breakdown.tsx`.
  - [x] Tạo `nowing_web/components/usage/usage-transactions.tsx`.
  - [x] Tạo `nowing_web/components/usage/date-range-picker.tsx`.
- [x] **Frontend: navigation & i18n** (AC 1)
  - [x] Thêm nav item "Usage" vào `nowing_web/components/layout/providers/LayoutDataProvider.tsx`.
  - [x] Thêm keys vào `nowing_web/messages/en.json`.
- [x] **Dependency**
  - [x] Thêm `recharts@3.9.2` vào `nowing_web/package.json` và chạy `pnpm install`.
- [x] **Tests**
  - [x] Backend integration tests cho `usage/summary`, `usage/time-series`, `usage/transactions`.
  - [x] Frontend `pnpm tsc --noEmit` pass.
  - [x] Playwright E2E scaffold `nowing_web/tests/usage/usage-dashboard.spec.ts` được giữ ở dạng `test.skip()` (E2E activation tùy chọn, chạy sau khi UI hoàn thiện).
- [x] **Lint & verify**
  - [x] `uv run ruff check --fix` và `uv run pytest tests/integration/usage/test_usage_dashboard.py` trong `nowing_backend`.
  - [x] `pnpm exec tsc --noEmit` và `pnpm exec biome check --write` trong `nowing_web`.

## Dev Notes

### Background

Dữ liệu usage và credit đã có đầy đủ ở backend:

- `TokenUsage` (`nowing_backend/app/db.py:1075-1140`): mỗi lần gọi LLM / capability billing ghi một row với `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_micros`, `model_breakdown`, `call_details`, `usage_type`, `workspace_id`, `user_id`, `created_at`.
- `User.credit_micros_balance` / `credit_micros_reserved` (`nowing_backend/app/db.py:2370-2383`): ví tín dụng thống nhất.
- `CreditPurchase` (`nowing_backend/app/db.py:2052-2092`): lịch sử mua credit qua Stripe.
- `PagePurchase` (`nowing_backend/app/db.py:2019-2049`): legacy page-purchase history.
- `UserIncentiveTask` (`nowing_backend/app/db.py:1985-2016`): credit thưởng từ GitHub/Reddit/Discord.

Các endpoint hiện có:

- `GET /api/v1/stripe/credit-status` (`stripe_routes.py:722-735`): trả về `credit_micros_balance`.
- `GET /api/v1/stripe/credit-purchases` (`stripe_routes.py:738-762`): lịch sử `CreditPurchase`.
- `GET /api/v1/stripe/purchases` (`stripe_routes.py:765-792`): lịch sử `PagePurchase`.
- `GET /api/v1/incentive-tasks` (`incentive_tasks_routes.py:29-70`): trạng thái và lịch sử incentive.
- `GET /api/v1/users/me` (`users_routes.py:17-22`): trả về `UserRead` (chỉ có `credit_micros_balance`, chưa có `credit_micros_reserved`).

Thiếu:

- Aggregate API để tổng hợp `TokenUsage` theo workspace, model, usage_type, provider.
- UI dashboard tổng hợp.

### Backend design

#### 1. New route file: `nowing_backend/app/routes/usage_routes.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal
from datetime import datetime, timedelta, UTC

from app.auth.context import AuthContext
from app.db import get_async_session, Permission
from app.users import get_auth_context, require_session_context
from app.utils.rbac import check_workspace_access
from app.schemas.usage import (
    UsageSummaryResponse,
    UsageTimeSeriesResponse,
    UsageTransactionsResponse,
)
from app.services.usage_service import UsageService

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    workspace_id: int = Query(..., ge=1),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    auth: AuthContext = Depends(require_session_context),
    session: AsyncSession = Depends(get_async_session),
):
    await check_workspace_access(session, auth, workspace_id)
    service = UsageService(session, auth.user)
    return await service.get_summary(workspace_id, start_date, end_date)


@router.get("/time-series", response_model=UsageTimeSeriesResponse)
async def get_usage_time_series(
    workspace_id: int = Query(..., ge=1),
    granularity: Literal["day", "week", "month"] = "day",
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    auth: AuthContext = Depends(require_session_context),
    session: AsyncSession = Depends(get_async_session),
):
    await check_workspace_access(session, auth, workspace_id)
    service = UsageService(session, auth.user)
    return await service.get_time_series(workspace_id, granularity, start_date, end_date)


@router.get("/transactions", response_model=UsageTransactionsResponse)
async def get_usage_transactions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    auth: AuthContext = Depends(require_session_context),
    session: AsyncSession = Depends(get_async_session),
):
    service = UsageService(session, auth.user)
    return await service.get_transactions(limit, offset)
```

**Lưu ý:** `require_session_context` từ `app/users.py:392` đảm bảo chỉ interactive session, không phải PAT.

#### 2. New service: `nowing_backend/app/services/usage_service.py`

Core logic:

```python
from sqlalchemy import select, func, text
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timedelta, UTC
from uuid import UUID

class UsageService:
    def __init__(self, session: AsyncSession, user: User):
        self.session = session
        self.user = user

    async def get_summary(
        self, workspace_id: int, start_date: datetime | None, end_date: datetime | None
    ) -> UsageSummaryResponse:
        # Default to last 30 days
        if not end_date:
            end_date = datetime.now(UTC)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Workspace usage totals
        result = await self.session.execute(
            select(
                func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(TokenUsage.cost_micros), 0).label("total_cost_micros"),
            )
            .filter(
                TokenUsage.workspace_id == workspace_id,
                TokenUsage.created_at >= start_date,
                TokenUsage.created_at <= end_date,
            )
        )
        totals = result.one()

        # Breakdown by usage_type
        usage_type_breakdown = await self._breakdown_by_usage_type(
            workspace_id, start_date, end_date
        )

        # Breakdown by model (from model_breakdown JSONB)
        model_breakdown = await self._breakdown_by_model(
            workspace_id, start_date, end_date
        )

        # Breakdown by provider (from model_breakdown JSONB)
        provider_breakdown = await self._breakdown_by_provider(
            workspace_id, start_date, end_date
        )

        return UsageSummaryResponse(
            current_balance_micros=self.user.credit_micros_balance,
            reserved_micros=self.user.credit_micros_reserved,
            total_tokens=totals.total_tokens,
            total_cost_micros=totals.total_cost_micros,
            start_date=start_date,
            end_date=end_date,
            by_usage_type=usage_type_breakdown,
            by_model=model_breakdown,
            by_provider=provider_breakdown,
        )
```

**Breakdown queries:**

- `by_usage_type`: group by `TokenUsage.usage_type`, sum `total_tokens` và `cost_micros`.
- `by_model`: explode `model_breakdown` JSONB keys. Ví dụ PostgreSQL query:
  ```sql
  SELECT
    key AS model,
    SUM((value->>'cost_micros')::bigint) AS cost_micros,
    SUM((value->>'total_tokens')::int) AS total_tokens
  FROM token_usage,
  LATERAL jsonb_each(model_breakdown)
  WHERE workspace_id = :ws_id
    AND created_at BETWEEN :start AND :end
  GROUP BY key
  ```
  Implement via SQLAlchemy `func.jsonb_each` hoặc native query.
- `by_provider`: similar nhưng group by `value->>'provider'`.

**Time series:**

- Group by date bucket (`date_trunc('day', created_at)`, `week`, `month`).
- Sum `cost_micros` và `total_tokens`.

**Transactions:**

- Query `CreditPurchase`, `PagePurchase`, `UserIncentiveTask` cho `user_id`.
- Union/merge thành một list sorted by `created_at` desc.
- Mỗi item có `type`, `amount_micros`, `description`, `status`, `created_at`.

#### 3. New schemas: `nowing_backend/app/schemas/usage.py`

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class UsageBreakdownItem(BaseModel):
    key: str
    total_tokens: int
    cost_micros: int


class UsageSummaryResponse(BaseModel):
    current_balance_micros: int
    reserved_micros: int
    total_tokens: int
    total_cost_micros: int
    start_date: datetime
    end_date: datetime
    by_usage_type: list[UsageBreakdownItem]
    by_model: list[UsageBreakdownItem]
    by_provider: list[UsageBreakdownItem]


class UsageTimeSeriesPoint(BaseModel):
    period: str  # ISO date hoặc week/month label
    total_tokens: int
    cost_micros: int


class UsageTimeSeriesResponse(BaseModel):
    granularity: str
    points: list[UsageTimeSeriesPoint]


class UsageTransactionItem(BaseModel):
    type: str  # "credit_purchase" | "page_purchase" | "incentive"
    amount_micros: int
    description: str | None
    status: str | None
    created_at: datetime


class UsageTransactionsResponse(BaseModel):
    transactions: list[UsageTransactionItem]
    total: int
```

### Frontend design

#### 1. New page

`nowing_web/app/dashboard/[workspace_id]/usage/page.tsx`:

```typescript
"use client";

import { UsageContent } from "./usage-content";

export default function UsagePage({ params }: { params: Promise<{ workspace_id: string }> }) {
	const { workspace_id } = use(params);
	return (
		<div className="mx-auto w-full max-w-5xl space-y-6 py-8">
			<UsageContent workspaceId={Number(workspace_id)} />
		</div>
	);
}
```

#### 2. Data fetching

Dùng `@tanstack/react-query` cho summary, time-series, transactions.

```typescript
const { data: summary, isLoading } = useQuery({
	queryKey: ["usage", "summary", workspaceId, dateRange],
	queryFn: () => usageApiService.getSummary({
		workspace_id: workspaceId,
		start_date: dateRange.start.toISOString(),
		end_date: dateRange.end.toISOString(),
	}),
	enabled: !!workspaceId,
});
```

#### 3. Component structure

- `UsageSummaryCards`: hiển thị balance, reserved, total tokens, total cost.
- `UsageChart`: line/bar chart dùng `recharts` (`ResponsiveContainer`, `LineChart`, `BarChart`, `XAxis`, `YAxis`, `Tooltip`).
- `UsageBreakdown`: 3 bảng/donut cho usage_type, model, provider.
- `UsageTransactions`: bảng lịch sử giao dịch.
- `DateRangePicker`: dùng `Calendar` với `mode="range"` hoặc preset buttons.

#### 4. Formatting

Sử dụng hàm `formatUsd` đã có trong `CreditBalanceDisplay.tsx` và `buy-credits-content.tsx`:

```typescript
function formatUsd(micros: number): string {
	const dollars = Math.max(0, micros) / 1_000_000;
	if (dollars >= 100) return `$${dollars.toFixed(0)}`;
	if (dollars >= 1) return `$${dollars.toFixed(2)}`;
	if (dollars > 0) return `$${dollars.toFixed(3)}`;
	return "$0.00";
}
```

**Ponytail note:** Hàm này bị duplicate giữa `CreditBalanceDisplay.tsx` và `buy-credits-content.tsx`. Trong story này, copy hàm vào `usage-content.tsx`. Nếu muốn refactor thành shared utility, làm ở story khác.

#### 5. Navigation

Thêm vào `nowing_web/components/layout/providers/LayoutDataProvider.tsx` trong `navItems`:

```typescript
const isUsageActive = pathname?.includes("/usage") === true;

{
	title: t("nav_menu.usage"), // hoặc "Usage"
	url: `/dashboard/${workspaceId}/usage`,
	icon: BarChart3,
	isActive: isUsageActive,
}
```

Icon `BarChart3` từ `lucide-react`.

### Routes registration

Thêm vào `nowing_backend/app/routes/__init__.py`:

```python
from .usage_routes import router as usage_router

router.include_router(usage_router)  # nên đặt gần stripe/incentive_tasks
```

### Tests

#### Backend integration tests

File gợi ý: `nowing_backend/tests/integration/usage/test_usage_dashboard.py`

- Tạo test user, workspace.
- Seed `TokenUsage` rows với nhiều `usage_type`, `model_breakdown`, `workspace_id`.
- Seed `CreditPurchase` và `UserIncentiveTask` rows.
- Gọi `GET /api/v1/usage/summary?workspace_id=...`:
  - Assert 200.
  - Assert totals khớp.
  - Assert breakdown by usage_type/model/provider.
  - Assert 403 khi user không thuộc workspace.
- Gọi `GET /api/v1/usage/time-series`:
  - Assert time buckets đúng `granularity`.
- Gọi `GET /api/v1/usage/transactions`:
  - Assert unified list sorted by `created_at` desc.

#### Frontend

- `pnpm tsc --noEmit` phải pass.
- E2E scaffold: `nowing_web/tests/usage/usage-dashboard.spec.ts` — verify page load, cards render.

### Edge cases & decisions

- **PAT vs session:** usage dashboard là interactive-only → dùng `require_session_context`.
- **Balance real-time:** `current_balance_micros` trong summary lấy từ `auth.user`. Sidebar vẫn dùng Zero để hiển thị real-time balance. Dashboard header có thể hiển thị sidebar balance hoặc summary balance; cả hai đều chính xác tại thời điểm fetch.
- **Model breakdown keys:** `model_breakdown` là JSONB dict keyed by model string. Nếu model name thay đổi giữa các versions, dashboard sẽ hiển thị như raw keys. Không cần normalize thêm.
- **No schema migration:** Story 8.3 không thêm cột mới. Nếu aggregation query chậm khi `token_usage` lớn, cân nhắc thêm composite index `(workspace_id, created_at)` trong migration tiếp theo.
- **Chart dependency:** `recharts` là dependency mới. Nếu không muốn thêm dependency, có thể thay bằng CSS bar chart/table, nhưng `recharts` phù hợp với yêu cầu dashboard.

### ATDD Artifacts

- Checklist: `_bmad-output/test-artifacts/atdd-checklist-8-3-usage-credit-dashboard-new-gap.md`
- Backend integration tests: `nowing_backend/tests/integration/usage/test_usage_dashboard.py`
- Frontend E2E tests: `nowing_web/tests/usage/usage-dashboard.spec.ts`

## Dev Agent Record

### Debug Log

- Backend integration tests initially failed vì test seed cả hai usage row dùng cùng `model_breakdown` key (`openai/gpt-4`), dẫn đến `by_model` cost tổng = 2000 thay vì 1500. Đã sửa test để `image_generation` dùng key `openai/dall-e-3`.
- `pnpm exec tsc --noEmit` báo lỗi type `Tooltip` formatter của `recharts` v3. Đã cast `value` về number và `label` về String.
- `pnpm lint` (Next.js lint) không chạy được trong project này; đã dùng `pnpm exec biome check --write` cho các file mới.

### Completion Notes

- Tất cả AC cơ bản đã được implement.
- Backend tests pass (7/7).
- Frontend `tsc` pass, Biome format pass.
- E2E Playwright scaffold còn `test.skip()`; chưa chạy vì cần backend chạy trong môi trường E2E.

## File List

- `nowing_backend/app/schemas/usage.py`
- `nowing_backend/app/services/usage_service.py`
- `nowing_backend/app/routes/usage_routes.py`
- `nowing_backend/app/routes/__init__.py`
- `nowing_backend/tests/integration/usage/conftest.py`
- `nowing_backend/tests/integration/usage/test_usage_dashboard.py`
- `nowing_web/contracts/types/usage.types.ts`
- `nowing_web/lib/apis/usage-api.service.ts`
- `nowing_web/app/dashboard/[workspace_id]/usage/page.tsx`
- `nowing_web/components/usage/usage-content.tsx`
- `nowing_web/components/usage/usage-chart.tsx`
- `nowing_web/components/usage/usage-breakdown.tsx`
- `nowing_web/components/usage/usage-transactions.tsx`
- `nowing_web/components/usage/date-range-picker.tsx`
- `nowing_web/components/layout/providers/LayoutDataProvider.tsx`
- `nowing_web/messages/en.json`
- `nowing_web/tests/usage/usage-dashboard.spec.ts`
- `nowing_web/package.json`
- `nowing_web/pnpm-lock.yaml`

## Change Log

- 2026-07-23: Implement Story 8.3 backend routes/service/schemas and frontend dashboard + navigation.
- 2026-07-23: Activate ATDD backend integration tests; all 7 pass.
- 2026-07-23: Update sprint-status.yaml and story file status to `done`.

### Review Findings

#### decision-needed

- [x] [Review][Decision] **Custom date range UI vs presets** — quyết định thêm `Calendar` với `mode="range"` vào `Popover` cạnh presets. Đã implement trong `date-range-picker.tsx`.
- [x] [Review][Decision] **Time-series granularity UI** — quyết định thêm `Tabs` Day/Week/Month trong header của chart. Đã implement trong `usage-content.tsx`.
- [x] [Review][Decision] **Playwright E2E activation** — quyết định giữ `test.skip()`; E2E activation cần backend chạy trong môi trường E2E và được xử lý ở giai đoạn QA/integration pipeline.
- [x] [Review][Decision] **PagePurchase trong transaction history** — giữ `PagePurchase` với `amount_micros` convert từ `amount_total` (cents → micros). Đã implement trong `usage_service.py`.

#### patch

- [x] [Review][Patch] **Time-series SQL dùng f-string interpolation** [`nowing_backend/app/services/usage_service.py:208-228`] — đã refactor dùng SQLAlchemy `func.to_char(func.timezone("UTC", created_at), ...)`; không còn nối chuỗi SQL.
- [x] [Review][Patch] **Timezone handling cho date range và time-series** [`usage_service.py:36-43`, `usage_routes.py:18-46`] — đã normalize mọi datetime về UTC trước khi query.
- [x] [Review][Patch] **`start_date > end_date` không validate** [`usage_service.py:36-43`, `usage_routes.py:23-30`] — đã raise `422` trong route và `ValueError` trong service.
- [x] [Review][Patch] **Model/provider breakdown crash với malformed JSONB** [`usage_service.py:131-151`, `167-187`] — đã dùng `jsonb_typeof` check trước khi cast, COALESCE 0 cho missing keys.
- [x] [Review][Patch] **Model/provider breakdown bỏ qua rows có `model_breakdown` rỗng** [`usage_service.py:131-151`, `167-187`] — đã dùng `COALESCE(NULLIF(..., '{}'::jsonb), '{}'::jsonb)` để tránh crash; behavior exclude empty object vẫn được ghi nhận.
- [x] [Review][Patch] **Empty state dựa trên `total_tokens` thay vì cost** [`nowing_web/components/usage/usage-content.tsx:54`] — đã check cả `total_tokens > 0` và `total_cost_micros > 0`.
- [x] [Review][Patch] **Date range picker không reflect selected value** [`nowing_web/components/usage/date-range-picker.tsx:12-17`] — đã dùng `value` prop để highlight preset đang chọn.
- [x] [Review][Patch] **Usage routes thiếu `response_model` và return type** [`nowing_backend/app/routes/usage_routes.py:18,32,49`] — đã thêm `response_model` và return type annotations.
- [x] [Review][Patch] **Nav item "Usage" hardcoded English** [`nowing_web/components/layout/providers/LayoutDataProvider.tsx:308-311`] — đã dùng `tNav("nav_menu.usage")`.
- [x] [Review][Patch] **Dashboard strings chưa localized** [`usage-content.tsx:68-100`] — đã thêm namespace `usage` trong `messages/en.json` và dùng `useTranslations("usage")`.
- [x] [Review][Patch] **Time-series chart chỉ hiển thị cost, không hiển thị tokens** [`usage-chart.tsx:45-56`] — đã dùng `ComposedChart` với `Bar` cost (trái) và `Line` tokens (phải).
- [x] [Review][Patch] **Backend integration tests thiếu `by_provider` và `PagePurchase`** [`test_usage_dashboard.py:20-89`, `197-226`] — đã bổ sung assertions `by_provider` và test `test_usage_transactions_includes_page_purchases`.
- [x] [Review][Patch] **`__pycache__` files trong diff** [`nowing_backend/tests/integration/usage/__pycache__/*`] — đã xoá thư mục.

#### defer

- [x] [Review][Defer] **Transaction pagination tải toàn bộ history vào memory** [`usage_service.py:248-317`] — deferred, cần optimize bằng UNION query khi transaction history lớn.
- [x] [Review][Defer] **Negative balance clamp `$0`** [`usage-content.tsx:15-21`] — deferred, balance/reserved negative không phải normal state hiện tại.
- [x] [Review][Defer] **GLOBAL_LLM_CONFIG_B64 pre-existing issues** [`nowing_backend/app/config/__init__.py:51-62`] — deferred, không liên quan Story 8.3.
- [x] [Review][Defer] **Sprint-status.yaml thay đổi ngoài scope 8.3** [`sprint-status.yaml:9-33`] — deferred, do context từ thread trước.
- [x] [Review][Defer] **Currency format helper duplicated 3 components** — deferred, refactor utility chung ở story cleanup.

#### dismissed

- **Credit balance trả về từ workspace-scoped endpoint** — by design, `User.credit_*` là per-user fields, workspace chỉ dùng để gating.
- **Test auth override `get_auth_context` vs `require_session_context`** — `require_session_context` sử dụng `get_auth_context` internally; tests pass.
- **`INCENTIVE_TASKS_CONFIG` import từ `app.db`** — by design, config được định nghĩa cùng `db.py`.
