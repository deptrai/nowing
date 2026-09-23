---
story_key: 21-8c-multi-domain-social-target-expansion
status: done
epic: 21
story: 8c
---

# Story 21.8c: Multi-Domain Social Target Expansion

**Status:** `done`  
**Epic:** Epic 21 — Lead Gen Intelligence  
**Governed by:** AD-SOC-9, AD-SOC-1  
**Split from:** Story 21.8 — Social Ingress via XActions Integration (baseline)

---

## Story

As a sales development representative,  
I want to create monitored targets for multiple platforms (Facebook, Twitter, TikTok, Chợ Tốt, Shopee, TopCV, VietnamWorks, LinkedIn, Batdongsan, Mã số thuế, B2B registry),  
so that I can ingest leads from any vertical source.

---

## Acceptance Criteria

1. **Target Creation** — **Given** `POST /workspaces/{id}/social-monitored-targets`, **When** payload includes any supported platform, **Then** the target is validated and persisted.
2. **Platform Support** — **Given** a target, **When** scheduler checks due targets, **Then** it supports `facebook_group`, `facebook_page`, `twitter_keyword`, `twitter_user`, `tiktok_hashtag`, `chotot_category`, `shopee_keyword`, `topcv_search`, `vietnamworks_search`, `linkedin_company`, `batdongsan_category`, `masothue_lookup`, `b2b_registry_search`.
3. **CRUD Endpoints** — **Given** an existing target, **When** a user calls `GET`/`PATCH`/`DELETE /workspaces/{id}/social-monitored-targets/{target_id}`, **Then** the endpoints return, update, or delete the target respecting workspace tenancy and `LEADS_WRITE` permission.
4. **Frontend Dropdown** — **Given** the social target form, **When** rendered, **Then** it shows the expanded platform dropdown with icons.

---

## Tasks / Subtasks

- [x] Task 1: Platform enum expansion
  - [x] 1.1 Update `SocialTargetCreate.platform` regex in `social_routes.py`.
  - [x] 1.2 Update `SUPPORTED_PLATFORMS` in `social_xactions_ingest.py` to 13 platforms.
  - [x] 1.3 Update DB enum and Alembic migration if needed.
- [x] Task 2: CRUD routes
  - [x] 2.1 Add `GET`, `PATCH`, `DELETE` endpoints to `social_routes.py`.
  - [x] 2.2 Add `SocialTargetUpdate`/`SocialTargetRead` schemas.
- [x] Task 3: Frontend
  - [x] 3.1 Update social target form with multi-platform dropdown.
  - [x] 3.2 Update connector/platform icons if needed.
- [x] Task 4: Tests
  - [x] 4.1 Unit tests for route validation.
  - [x] 4.2 Integration tests for CRUD.

---

## Dev Notes

- `facebook_page` and `twitter_user` are P0 hotfix targets; the rest are P2 expansion.
- Requires XActions to expose generic `x_scrape` or thin-event stream for all crawlers (A1/A2 in integration plan). Until then, fall back to `x_crawl_post` with `url` args per platform.
- Do not implement scraping logic in Nowing.

### References

- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-09-09-xactions-21-8-correction.md]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-xactions-social-integration-2026-08-15/INTEGRATION-PLAN-2026-09-09.md]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-xactions-social-integration-2026-08-15/ARCHITECTURE-SPINE.md]
- [Code: nowing_backend/app/routes/social_routes.py]
- [Code: nowing_backend/app/tasks/celery_tasks/social_xactions_ingest.py]
