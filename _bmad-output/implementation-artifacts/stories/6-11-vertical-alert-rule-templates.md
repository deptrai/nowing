---
story_key: 6-11-vertical-alert-rule-templates
status: ready-for-dev
baseline_commit: 098260ef9
epic: 6
story: 11
---

# Story 6.11: Vertical Alert Rule Templates

**Status:** `ready-for-dev`  
**Epic:** 6 — Automations  
**Governed by:** AD-33 (Generic Alert Engine), AD-34, AD-35, FR-44/49/50/51/52, `epics.md` lines 4075–4110.  
**Consolidated from:** Story 14.3 (News Alerts), Story 15.3 (Stock Price Alerts), Story 16.3 (Company Alerts), Story 17.3 (Price Drop Alerts), Story 17.4 (Competitor Tracking).

---

## Story

As a **researcher or analyst**,  
I want pre-configured alert rule templates for vertical domains (news topic monitoring, stock price crossing, corporate registry status changes, e-commerce price drops, and competitor tracking) built on top of the Generic Alert Engine (Story 6.8),  
so that I can activate intelligent scheduled monitoring in 1 click without manually configuring capability schemas, diff strategies, or query parameters.

---

## Acceptance Criteria

### AC-1 — Vertical Alert Template Catalog & Registration
**Given** the alert engine backend,  
**When** a client requests available alert templates via `GET /workspaces/{workspace_id}/alerts/templates`,  
**Then** it returns the registered vertical templates:
1. `news_topic_monitoring` — Category: `news`, `capability_id`: `news.rss` (or `google_search.scrape`), `diff_strategy`: `new_items`, schedule default: `daily`.
2. `stock_price_threshold` — Category: `finance`, `capability_id`: `cafef.scrape` (or `vietstock.scrape`), `diff_strategy`: `price_change` (or `threshold_cross`), schedule default: `daily`.
3. `company_status_change` — Category: `company`, `capability_id`: `masothue.scrape`, `diff_strategy`: `threshold_cross`, schedule default: `weekly`.
4. `ecommerce_price_drop` — Category: `ecommerce`, `capability_id`: `shopee.scrape`, `diff_strategy`: `price_change`, schedule default: `daily`.
5. `competitor_item_tracking` — Category: `ecommerce`, `capability_id`: `shopee.scrape`, `diff_strategy`: `new_items`, schedule default: `daily`.

### AC-2 — Capability Availability & Pre-flight Validation
**Given** a vertical template requiring a specific capability,  
**When** the template catalog is generated or a template is instantiated,  
**Then** the engine checks `CapabilityRegistry`:
- If the required capability is registered, the template has `is_available: true`.
- If the required capability is missing or not registered in the environment (e.g. `lazada.scrape`), the template returns `is_available: false` with `unavailable_reason`. Instantiating an unavailable template returns `400 Bad Request` with error code `CAPABILITY_UNAVAILABLE`.

### AC-3 — 1-Click Rule Instantiation from Template
**Given** an authenticated user with `alerts:write` (or `automations:write`) permission in the workspace,  
**When** they send `POST /workspaces/{workspace_id}/alerts/from-template`,  
**With** payload:
```json
{
  "template_id": "stock_price_threshold",
  "name": "Vinamilk (VNM) Stock Drop Alert",
  "parameters": {
    "symbol": "VNM",
    "price_threshold": 65000,
    "direction": "below"
  },
  "schedule": "daily",
  "notification_channels": ["in_app", "telegram"]
}
```
**Then** the backend:
1. Validates the template parameters against the template's parameter schema.
2. Resolves and populates `capability_id`, `diff_strategy`, `query`, `threshold`, and `notification_channels`.
3. Inserts a standard `AlertRule` row in the database scoped to `workspace_id`.
4. Auto-subscribes the requesting user in `alert_subscriptions` (channel `in_app`).
5. Returns `201 Created` with the newly created `AlertRuleRead`.

### AC-4 — Diff Strategy & Old-vs-New Notification Payload
**Given** an alert rule instantiated from a vertical template,  
**When** the rule is executed by Celery Beat / `tick.py` and a diff is detected:
- For `new_items`: new items are listed with title, link, and publication date.
- For `price_change`: notification payload includes `old_price`, `new_price`, `delta`, and `percentage_change`.
- For `threshold_cross`: notification payload highlights the crossed value vs threshold.
**And** notifications dispatched to `in_app` or `telegram` include direct reference links and clear human-readable trigger reasons.

### AC-5 — Frontend Vertical Templates UI & Integration
**Given** the workspace alert/saved searches interface in `nowing_web`,  
**When** navigating to the Alert Rules or Research section,  
**Then** users see a "Create from Template" dialog/drawer listing available vertical templates with domain icons, descriptions, parameter inputs (e.g., ticker symbol, keyword, product URL), and instant validation before creating.

### AC-6 — Test Coverage
**Given** the template engine and API routes,  
**When** test suites execute,  
**Then**:
- Unit tests cover template registry, parameter compilation, capability gating, and template validation.
- Integration tests cover `GET /alerts/templates` and `POST /alerts/from-template` lifecycle, duplicate naming validation, and permission checks.
- All tests pass with 100% ruff clean.

---

## Tasks / Subtasks

- [ ] Backend Template Architecture (`app/alerts/templates/`)
  - [ ] Define `AlertTemplate` data structures and metadata (id, name, description, category, required_capability, diff_strategy, default_schedule, parameter_schema).
  - [ ] Implement `VerticalAlertTemplateRegistry` with built-in templates (News, Stock, Company, E-commerce Price Drop, Competitor Tracking).
  - [ ] Implement parameter compiler transforming template inputs into valid `AlertRuleCreate` payload.
- [ ] Backend Routes & API
  - [ ] Add `GET /workspaces/{workspace_id}/alerts/templates` to `app/routes/alert_rules_routes.py`.
  - [ ] Add `POST /workspaces/{workspace_id}/alerts/from-template` route with validation and auto-subscription.
- [ ] Frontend Contracts & Service
  - [ ] Add TypeScript interfaces to `contracts/types/alert-rules.types.ts`.
  - [ ] Extend `adminHealthApiService` / `alertRulesApiService` with template endpoints.
  - [ ] Add "Create from Template" UI modal or card selector in `nowing_web`.
- [ ] Verification & Tests
  - [ ] Write unit tests in `nowing_backend/tests/unit/alerts/test_alert_templates.py`.
  - [ ] Write integration test in `nowing_backend/tests/integration/alerts/test_alert_templates_routes.py`.
  - [ ] Run `ruff check` and pytest suite.
