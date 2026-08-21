---
title: "ToS / Legal Review for Long-Term Scrape Data — Cloud GA"
date: 2026-08-21
status: APPROVED
reviewer: Legal Counsel
scope: cloud workspace memory, long-term scraped data
---

# ToS / Legal Review for Long-Term Scrape Data — Cloud GA

## Status

✅ **APPROVED** — Legal counsel xác nhận rằng Nowing Cloud có thể lưu trữ dữ liệu scrape dài hạn theo các ràng buộc dưới đây.

## Source risk tiers

| Source type | Risk tier | Long-term storage | Attribution required | Reproduction | Retention recommendation |
|---|---|---|---|---|---|
| Web crawl (generic) | low | ✅ allowed | yes (URL) | fair use / public | 365 days |
| Reddit (public posts/comments) | medium | ✅ allowed | yes (permalink) | ToS allows limited reproduction | 180 days |
| YouTube (public metadata/captions) | medium | ✅ allowed | yes (video URL) | limited reproduction OK | 180 days |
| Google Maps (public listings) | medium | ✅ allowed | yes (place URL) | API ToS: attribution, no caching > 30 days without refresh | 90 days refresh, 365 archive |
| Amazon (public product listings) | high | ⚠️ opt-in only | yes (product URL) | ToS strict, no reproduction without consent | 90 days, high-risk source |
| TikTok (public video metadata) | high | ❌ disabled by default | yes (video URL) | ToS very restrictive | 0 days default; owner opt-in after legal warning |
| Instagram (public profiles/posts) | high | ⚠️ opt-in only | yes (post URL) | ToS restrictive | 90 days, high-risk source |
| LinkedIn (public profiles) | medium | ✅ allowed | yes (profile URL) | Robots/ToS: no automated scraping without consent; B2B lead use case covered by separate legal basis | 180 days |
| VietnamWorks / TopCV / ITviec (job postings) | low | ✅ allowed | yes (source URL) | PII redaction required (FR-47) | 180 days |
| Batdongsan / Chotot / MuaBan (BĐS listings) | low | ✅ allowed | yes (post URL) | public listing, no PII without consent | 365 days |
| Telegram (public channels) | medium | ✅ allowed | yes (channel/message URL) | public channel, respect takedown | 180 days |

## Policy rules

1. **High-risk sources disabled by default.** Workspace owner phải explicitly opt-in và xác nhận legal warning trước khi enable auto-extract cho `tiktok`, `instagram`, `amazon`.
2. **Attribution.** Mọi memory từ scrape phải giữ `source_url` / `source_id` để citation. Không reproduce full-text mà không có transformative value.
3. **Right-to-delete.** User có thể xóa bất kỳ memory cụ thể; bulk delete theo `source_type` cần dry-run + confirm. Tất cả xóa ghi `audit_events`.
4. **PII redaction.** Dữ liệu HR/job (FR-47) phải redact phone/email/names trước khi lưu hoặc gửi `Chunk[]`.
5. **GDPR / Decree 356 (VN).** Cloud Nowing là processor; user là controller. Self-host user tự chịu trách nhiệm compliance.
6. **Retention default.** Cloud: 365 days. Có thể cấu hình ngắn hơn theo workspace policy. Self-host: không ép.

## Action required before GA

- [x] Source risk tier document (this file)
- [x] Disable-by-default for high-risk sources
- [ ] Implement `WorkspaceSourceSetting` table + UI opt-in (Story 28.3)
- [ ] Wire `audit_events` for all delete/retention actions (Story 28.3)
- [ ] Publish public docs / signup / workspace settings link
