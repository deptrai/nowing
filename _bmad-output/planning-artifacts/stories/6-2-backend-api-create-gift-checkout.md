# Story 6.2: Backend API — Endpoint Tạo Gift Checkout

Status: done

## Story

As a Người dùng đã đăng nhập,
I want gọi API để tạo Stripe Checkout session cho việc mua gift,
So that tôi được redirect sang trang thanh toán Stripe an toàn để hoàn tất việc mua quà.

## Acceptance Criteria

1. `POST /api/v1/stripe/create-gift-checkout` với body `{"plan_id": "pro_monthly", "duration_months": 3}` (JWT required) trả về `{"checkout_url": "https://checkout.stripe.com/...", "admin_approval_mode": false}`.
2. Backend tạo Stripe Checkout Session với `mode="payment"`, `price_data` động (không cần pre-created price ID), `metadata.purchase_type="gift"`, `metadata.purchaser_id`, `metadata.plan_id`, `metadata.duration_months`.
3. Giá được tính đúng theo `GIFT_PRICING` config (khớp với subscription pricing):
   - `pro_monthly`: `{1: 1200, 3: 3600, 6: 7200, 12: 9600}` → $12 / $36 / $72 / $96 (gói 12 tháng = annual rate, tiết kiệm $48).
   - `max_monthly`: `{1: 10000, 3: 30000, 6: 60000, 12: 96000}` → $100 / $300 / $600 / $960 (gói 12 tháng = annual rate, tiết kiệm $240).
4. `plan_id` không có trong `GIFT_PRICING` → `400 Bad Request` với detail rõ ràng.
5. `duration_months` không có trong config cho plan đó → `400 Bad Request`.
6. Khi Stripe chưa cấu hình (`STRIPE_SECRET_KEY` trống) → `admin_approval_mode=True`, `checkout_url=""` — không throw exception.
7. Endpoint được thêm vào `nowing_backend/app/routes/stripe_routes.py`, schema thêm vào `nowing_backend/app/schemas/stripe.py`.
8. Không thay đổi bất kỳ endpoint nào hiện có (`create-token-topup-checkout`, `create-subscription-checkout`, webhook, v.v.).

## Tasks / Subtasks

- [x] Thêm `GIFT_PRICING` config vào `nowing_backend/app/config/__init__.py` (AC: 3)
  - [x] Thêm vào class `Settings` (cùng nơi với `TOKEN_PACKS` ~line 324): `GIFT_PRICING: dict[str, dict[int, int]] = {"pro_monthly": {1: 1200, 3: 3600, 6: 7200, 12: 9600}, "max_monthly": {1: 10000, 3: 30000, 6: 60000, 12: 96000}}` — giá khớp subscription (Pro $12/mo, $96/yr; Max $100/mo, $960/yr).
  - [x] Không cần env var — pricing là hardcoded business logic

- [x] Thêm Pydantic schemas vào `nowing_backend/app/schemas/stripe.py` (AC: 1, 6)
  - [x] `CreateGiftCheckoutRequest(BaseModel)`: `plan_id: str`, `duration_months: int = Field(ge=1, le=12)`
  - [x] `CreateGiftCheckoutResponse(BaseModel)`: `checkout_url: str`, `admin_approval_mode: bool = False`

- [x] Thêm helper `_get_gift_urls(search_space_id: int)` vào `stripe_routes.py` (AC: 2)
  - [x] Pattern giống `_get_token_topup_urls()`: success → `/dashboard/{id}/purchase-success?session_id={CHECKOUT_SESSION_ID}`, cancel → `/dashboard/{id}/purchase-cancel`

- [x] Thêm endpoint `POST /create-gift-checkout` vào `stripe_routes.py` (AC: 1–6)
  - [x] Đặt SAU `create-token-topup-checkout` (~line 572), TRƯỚC `_queue_subscription_approval_request`
  - [x] Validate `plan_id` và `duration_months` từ `config.GIFT_PRICING` → 400 nếu không hợp lệ
  - [x] Admin-approval fallback nếu `not config.STRIPE_SECRET_KEY`
  - [x] Gọi `stripe_client.v1.checkout.sessions.create()` với `mode="payment"`, `price_data` động, `metadata.purchase_type="gift"`
  - [x] Try/except `StripeError` → fallback `admin_approval_mode=True`
  - [x] Thêm `CreateGiftCheckoutRequest`, `CreateGiftCheckoutResponse` vào `import` section của `stripe_routes.py`

- [x] Verify
  - [x] `uv run pytest tests/unit/ -q --ignore=tests/unit/connectors/test_dexscreener_connector.py --ignore=tests/unit/indexing_pipeline/` → **408 passed** (1 pre-existing dexscreener error không liên quan)

### Review Findings

- [x] [Review][Decision] GIFT_PRICING `pro_monthly` và `pro_yearly` có giá identical — **Resolved: Intentional.** Gift là "tier × duration"; monthly/yearly label chỉ matter lúc recipient redeem (webhook 6.3 sẽ set plan tier tương ứng). Đổi giá sẽ conflict với logic redeem. Giữ nguyên theo spec. [config/__init__.py:340-346]
- [x] [Review][Decision] `plan_id: str` vs `PlanId` enum — **Resolved: Giữ `str`.** Convert sang `class PlanId(str, Enum)` có risk subtle: f-string trả về `"PlanId.pro_monthly"` thay vì `"pro_monthly"` → metadata sai → webhook 6.3 crash. GIFT_PRICING lookup đã validate đầy đủ, giữ spec-compliance. [schemas/stripe.py:33]
- [x] [Review][Patch] `except (StripeError, HTTPException)` âm thầm nuốt 503 từ `_get_gift_urls` — **Fixed**: đổi thành `except StripeError` only [stripe_routes.py:750]
- [x] [Review][Patch] Docstring `create_gift_checkout` chỉ nói fallback khi `STRIPE_SECRET_KEY` trống — **Fixed**: docstring đã cập nhật để reflect cả hai fallback paths [stripe_routes.py:665]
- [x] [Review][Defer] `/dashboard/0/purchase-success` trigger onboarding redirect loop — frontend 6.6 cần handle `search_space_id=0` hoặc gift có flow riêng [stripe_routes.py:707] — deferred, cần fix ở frontend Story 6.6
- [x] [Review][Defer] `purchase-success/page.tsx` hard-coded "Tokens added!" copy — gift purchaser thấy message sai [nowing_web/app/dashboard/[search_space_id]/purchase-success/page.tsx:31-47] — deferred, cần fix ở frontend Story 6.6
- [x] [Review][Defer] Webhook chưa handle `purchase_type="gift"` — nếu 6.2 deploy trước 6.3, payment đã thu nhưng không tạo gift_code [stripe_routes.py:~989] — deferred, sẽ được Story 6.3 implement; cần deploy cùng nhau
- [x] [Review][Defer] `duration_months: int = Field(ge=1, le=12)` wider hơn dict keys (1/3/6/12) — 2/4/5/7-11 pass Pydantic rồi fail 400 ở lookup [schemas/stripe.py:33] — deferred, có thể tighten thành `Literal[1,3,6,12]`
- [x] [Review][Defer] `customer_email=user.email` tạo duplicate Stripe customer khi user đã có Stripe customer linked — cross-cutting với token-topup/subscription [stripe_routes.py:740] — deferred, cross-cutting concern
- [x] [Review][Defer] `checkout_url: str` (required) nhưng admin_approval_mode trả `""` — contract nên `Optional[str] = None` [schemas/stripe.py:40] — deferred, cross-cutting với sibling endpoints
- [x] [Review][Defer] Gift checkout không có authorization/eligibility check — anyone authenticated có thể buy, không chống abuse [stripe_routes.py:658] — deferred, cần policy story riêng
- [x] [Review][Defer] `_get_gift_urls` và `_get_token_topup_urls` trùng logic — drift risk [stripe_routes.py:85-95] — deferred, DRY refactor
- [x] [Review][Defer] Không có idempotency cho rapid double-clicks — 2 Stripe sessions, 2 PI, 2 gift_codes tạo — [stripe_routes.py:700-748] — deferred, cross-cutting với token-topup

## Dev Notes

### Files cần thay đổi

1. `nowing_backend/app/config/__init__.py` — thêm `GIFT_PRICING`
2. `nowing_backend/app/schemas/stripe.py` — thêm `CreateGiftCheckoutRequest`, `CreateGiftCheckoutResponse`
3. `nowing_backend/app/routes/stripe_routes.py` — thêm helper + endpoint

### Pattern cho config — PHẢI tuân thủ

Cùng block với `TOKEN_PACKS` (line ~324 trong class `Settings`):

```python
# Gift subscription pricing (cents): plan_id → duration_months → amount_cents
GIFT_PRICING: dict[str, dict[int, int]] = {
    # Aligned with subscription pricing (pricing-section.tsx):
    # Pro: $12/mo, $96/yr (annual rate) — save $48
    # Max: $100/mo, $960/yr (annual rate) — save $240
    "pro_monthly": {1: 1200, 3: 3600, 6: 7200, 12: 9600},
    "max_monthly": {1: 10000, 3: 30000, 6: 60000, 12: 96000},
}
```

### Pattern cho Pydantic schemas — PHẢI tuân thủ

Thêm vào `nowing_backend/app/schemas/stripe.py` (sau `CreateTokenTopupResponse`):

```python
class CreateGiftCheckoutRequest(BaseModel):
    """Request body for creating a Stripe gift subscription checkout session."""

    plan_id: str = Field(description="Subscription plan to gift (e.g. 'pro_monthly').")
    duration_months: int = Field(ge=1, le=12, description="Gift duration in months.")


class CreateGiftCheckoutResponse(BaseModel):
    """Response containing the Stripe-hosted gift checkout URL."""

    checkout_url: str
    admin_approval_mode: bool = False
```

### Pattern cho helper URL — PHẢI tuân thủ

Thêm vào `stripe_routes.py` cạnh `_get_token_topup_urls()` (line ~73):

```python
def _get_gift_urls(search_space_id: int) -> tuple[str, str]:
    """Return (success_url, cancel_url) for gift checkout."""
    if not config.NEXT_FRONTEND_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEXT_FRONTEND_URL is not configured.",
        )
    base_url = config.NEXT_FRONTEND_URL.rstrip("/")
    success_url = f"{base_url}/dashboard/{search_space_id}/purchase-success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/dashboard/{search_space_id}/purchase-cancel"
    return success_url, cancel_url
```

### Pattern cho endpoint — PHẢI tuân thủ

```python
@router.post("/create-gift-checkout", response_model=CreateGiftCheckoutResponse)
async def create_gift_checkout(
    body: CreateGiftCheckoutRequest,
    user: User = Depends(current_active_user),
) -> CreateGiftCheckoutResponse:
    """Create a Stripe Checkout Session for purchasing a gift subscription.

    Uses Stripe price_data so no pre-created price IDs are required.
    When Stripe is not configured (no STRIPE_SECRET_KEY), returns admin_approval_mode=True.
    """
    # Validate plan_id and duration_months against GIFT_PRICING config
    plan_pricing = config.GIFT_PRICING.get(body.plan_id)
    if not plan_pricing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan_id '{body.plan_id}'. Valid plans: {list(config.GIFT_PRICING)}",
        )
    amount_cents = plan_pricing.get(body.duration_months)
    if amount_cents is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid duration_months {body.duration_months} for plan '{body.plan_id}'. "
                   f"Valid durations: {sorted(plan_pricing)}",
        )

    # Admin-approval mode: Stripe not configured
    if not config.STRIPE_SECRET_KEY:
        logger.info(
            "Gift checkout admin-approval mode: no Stripe key, user %s requested %s x%d months",
            user.id,
            body.plan_id,
            body.duration_months,
        )
        return CreateGiftCheckoutResponse(checkout_url="", admin_approval_mode=True)

    stripe_client = get_stripe_client()

    # search_space_id not relevant for gift — use 0 as placeholder for URLs
    # (success page just shows "payment complete", no search space needed)
    success_url, cancel_url = _get_gift_urls(0)

    plan_label = body.plan_id.replace("_", " ").title()

    try:
        checkout_session = stripe_client.v1.checkout.sessions.create(
            params={
                "mode": "payment",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "line_items": [
                    {
                        "price_data": {
                            "currency": "usd",
                            "unit_amount": amount_cents,
                            "product_data": {
                                "name": f"Nowing Gift — {plan_label} × {body.duration_months} month(s)",
                                "description": (
                                    f"Gift subscription: {plan_label} for {body.duration_months} month(s). "
                                    "The recipient can redeem this gift code in their account settings."
                                ),
                            },
                        },
                        "quantity": 1,
                    }
                ],
                "client_reference_id": str(user.id),
                "customer_email": user.email,
                "metadata": {
                    "purchase_type": "gift",
                    "purchaser_id": str(user.id),
                    "plan_id": body.plan_id,
                    "duration_months": str(body.duration_months),
                    "amount_cents": str(amount_cents),
                },
            }
        )
    except (StripeError, HTTPException) as exc:
        logger.warning(
            "Stripe gift checkout failed for user %s, falling back to admin-approval: %s",
            user.id,
            exc,
        )
        return CreateGiftCheckoutResponse(checkout_url="", admin_approval_mode=True)

    checkout_url = getattr(checkout_session, "url", None)
    if not checkout_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe checkout session did not return a URL.",
        )

    return CreateGiftCheckoutResponse(checkout_url=checkout_url)
```

### Import cần thêm vào `stripe_routes.py`

Thêm vào block `from app.schemas.stripe import (` (line ~24):

```python
from app.schemas.stripe import (
    BillingPortalResponse,
    CreateGiftCheckoutRequest,      # NEW
    CreateGiftCheckoutResponse,     # NEW
    CreateSubscriptionCheckoutRequest,
    CreateSubscriptionCheckoutResponse,
    CreateTokenTopupRequest,
    CreateTokenTopupResponse,
    PlanId,
    StripeStatusResponse,
    StripeWebhookResponse,
)
```

### Webhook — KHÔNG THAY ĐỔI trong story này

Story 6.3 sẽ thêm `_fulfill_gift_purchase()` và xử lý `purchase_type == "gift"` trong webhook. Story 6.2 chỉ tạo checkout session — không cần touch webhook handler.

### Admin-approval flow — context từ story 6.5

Khi `admin_approval_mode=True` (Stripe chưa cấu hình), frontend Story 6.6 sẽ hiển thị message khác biệt. Story 6.5 sẽ thêm `POST /api/v1/stripe/create-gift-request` cho admin-approval path. Story 6.2 chỉ cần return `admin_approval_mode=True` — không cần gọi gift request.

### search_space_id trong gift URLs

Gift purchase không gắn với một search space cụ thể (khác token topup). Dùng `0` làm placeholder cho URL: `/dashboard/0/purchase-success`. Frontend story 6.6 sẽ handle redirect phù hợp. Alternatively, nếu muốn thêm `search_space_id` vào request body, đây là optional improvement — không required cho story này.

### Dependency: Story 6.1 (đã done)

Story này KHÔNG cần bảng `gift_codes` — chỉ tạo Stripe checkout session. Migration 132 (story 6.1) cần phải đã được chạy trước khi story 6.3 (webhook fulfillment) được implement.

### Verification command

```bash
cd nowing_backend
uv run pytest tests/unit/ -q \
  --ignore=tests/unit/connectors/test_dexscreener_connector.py \
  --ignore=tests/unit/indexing_pipeline/
```

### Project Structure Notes

- Thêm config: `nowing_backend/app/config/__init__.py` (line ~330, sau `TOKEN_PACKS`)
- Thêm schemas: `nowing_backend/app/schemas/stripe.py`
- Thêm endpoint: `nowing_backend/app/routes/stripe_routes.py` (sau `create-token-topup-checkout`, ~line 645)
- Không tạo file mới

### References

- [Source: nowing_backend/app/routes/stripe_routes.py#572-641] — `create_token_topup_checkout` pattern
- [Source: nowing_backend/app/routes/stripe_routes.py#73-91] — `_get_token_topup_urls` + `_get_subscription_urls` patterns
- [Source: nowing_backend/app/schemas/stripe.py] — schema patterns
- [Source: nowing_backend/app/config/__init__.py#324-340] — `TOKEN_PACKS` config pattern
- [Source: _bmad-output/planning-artifacts/epics.md#Story-6.2] — AC gốc từ Epic

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Debug Log References

- pytest tests/unit/ → 408 passed, 1 pre-existing dexscreener error (không liên quan story này)

### Completion Notes List

- `GIFT_PRICING` được thêm vào `config/__init__.py` sau `TOKEN_PACKS` — hardcoded business logic, không cần env var
- Schemas `CreateGiftCheckoutRequest`/`CreateGiftCheckoutResponse` thêm vào `schemas/stripe.py` sau `CreateTokenTopupResponse`
- `_get_gift_urls(search_space_id)` helper dùng lại pattern của `_get_token_topup_urls` — success URL chứa `{CHECKOUT_SESSION_ID}` placeholder cho Stripe, cancel URL trỏ `/dashboard/{id}/purchase-cancel`. Gift purchase không gắn search space cụ thể → dùng `search_space_id=0` làm placeholder (frontend story 6.6 sẽ handle redirect)
- Endpoint `POST /create-gift-checkout` validate `plan_id` + `duration_months` từ `config.GIFT_PRICING`, trả 400 với detail chứa danh sách hợp lệ khi không match
- Stripe fallback: khi `STRIPE_SECRET_KEY` trống hoặc `stripe_client.v1.checkout.sessions.create` raise `StripeError`/`HTTPException` → return `admin_approval_mode=True, checkout_url=""` thay vì crash
- Checkout session dùng `mode="payment"` + `price_data` động (không cần pre-created price IDs), `metadata.purchase_type="gift"` để webhook (story 6.3) dispatch đúng branch
- Không thay đổi bất kỳ endpoint existing nào (`create-token-topup-checkout`, `create-subscription-checkout`, webhook)

### File List

- `nowing_backend/app/config/__init__.py` (modified — thêm `GIFT_PRICING`)
- `nowing_backend/app/schemas/stripe.py` (modified — thêm `CreateGiftCheckoutRequest`, `CreateGiftCheckoutResponse`)
- `nowing_backend/app/routes/stripe_routes.py` (modified — thêm `_get_gift_urls`, `create_gift_checkout`)
