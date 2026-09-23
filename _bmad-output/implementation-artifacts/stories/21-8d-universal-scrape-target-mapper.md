---
story_key: 21-8d-universal-scrape-target-mapper
status: done
epic: 21
story: 8d
---

# Story 21.8d: Universal Scrape Target Mapper

**Status:** `done`  
**Epic:** Epic 21 — Lead Gen Intelligence  
**Governed by:** AD-SOC-9, AD-SOC-4  
**Split from:** Story 21.8 — Social Ingress via XActions Integration (baseline)

---

## Story

As a Nowing backend engineer,  
I want a mapper that converts a `SocialMonitoredTarget` into the correct XActions tool and arguments,  
so that the scheduler can dispatch any platform without per-platform `if/else` blocks.

---

## Acceptance Criteria

1. **Tool Mapping** — **Given** a target with `platform` and `target_id`, **When** `UniversalScrapeTargetMapper.map(target)` runs, **Then** it returns `(tool_name, arguments)` for the matching XActions tool.
2. **Facebook Mapping** — **Given** Facebook group/page, **When** mapped, **Then** it returns `x_facebook_group_posts` or `x_facebook_posts`.
3. **Twitter Mapping** — **Given** Twitter keyword/user, **When** mapped, **Then** it returns `x_search_tweets` or `x_get_tweets`.
4. **VN Domain Mapping** — **Given** any other supported platform, **When** mapped, **Then** it returns `x_scrape(platform, action, args)` or `x_crawl_post` fallback.
5. **Chat Meta-Tool Mapping** — **Given** a chat agent calls `x_search`, `x_scrape`, or `x_crawl_post`, **When** arguments are validated, **Then** they are dispatched to the correct low-level XActions tool.

---

## Tasks / Subtasks

- [x] Task 1: Social target mapper
  - [x] 1.1 Implement `UniversalScrapeTargetMapper` in `app/proprietary/platforms/xactions/mapper.py`.
  - [x] 1.2 Add arg builders for all 13 platforms (see Dev Notes for VN-domain args).
  - [x] 1.3 Wire mapper into `social_xactions_ingest.py`.
- [x] Task 2: Chat gateway mapping
  - [x] 2.1 Create `xactions_gateway.py` dispatch for `x_search`, `x_scrape`, `x_crawl_post`.
  - [x] 2.2 Platform normalization (`_normalize_platform`, `_detect_platform_from_url`).
- [x] Task 3: Tests
  - [x] 3.1 Unit test `UniversalScrapeTargetMapper` for all 13 platforms.
  - [x] 3.2 Unit test `test_xactions_gateway.py` for chat meta-tools.

---

## Dev Notes

- VN-domain action args (for `x_scrape` dispatch):
  - `tiktok_hashtag` → `{platform:"tiktok", action:"posts", hashtag:t.target_id}`
  - `chotot_category` → `{platform:"chotot", action:"posts", category:t.target_id}`
  - `shopee_keyword` → `{platform:"shopee", action:"search", keyword:t.target_id}`
  - `topcv_search` / `vietnamworks_search` → `{platform, action:"search", query:t.target_id}`
  - `linkedin_company` → `{platform:"linkedin", action:"company", company:t.target_id}`
  - `batdongsan_category` → `{platform:"batdongsan", action:"posts", category:t.target_id}`
  - `masothue_lookup` → `{platform:"masothue", action:"lookup", taxCode:t.target_id}`
  - `b2b_registry_search` → `{platform:"b2b_registry", action:"search", query:t.target_id}`
- If XActions has not exposed `x_scrape`, fall back to `x_crawl_post` with `url` args; do not implement scraping in Nowing.

### References

- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-09-09-xactions-21-8-correction.md]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-xactions-social-integration-2026-08-15/INTEGRATION-PLAN-2026-09-09.md]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-xactions-social-integration-2026-08-15/ARCHITECTURE-SPINE.md]
- [Code: nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py]
- [Code: nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/xactions_gateway.py]
