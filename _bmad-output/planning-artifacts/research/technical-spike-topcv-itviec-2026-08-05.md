---
title: Technical Spike — TopCV & ITviec Scrapers
project: Nowing
date: 2026-08-05
author: Mary (Business Analyst) for Luisphan
status: recon done 2026-08-05; TopCV anti-bot POC pending; ITviec salary strategy pending
---

# Technical Spike: TopCV & ITviec Scrapers

## 1. Objectives

Xác nhận khả năng crawl TopCV và ITviec trước khi đưa vào P0:

1. TopCV có bị chặn bởi Cloudflare/anti-bot không? Cần headless browser / proxy không?
2. ITviec có phục vụ HTML server-rendered, dễ parse không?
3. Schema và selectors của ITviec là gì?
4. Có thể lấy job list + detail page từ ITviec không?
5. PII trong ITviec JD không?

## 2. TopCV — Initial Recon

### 2.1 Method

- `GET https://www.topcv.vn/tim-viec-lam-data-engineer`
- `GET https://www.topcv.vn/viec-lam/data-engineer`
- Headers: real browser `User-Agent`, `Accept`, `Accept-Language`, `Sec-Fetch-*`.

### 2.2 Findings

| Test | Result |
|---|---|
| Direct curl | **HTTP 403** |
| Python `requests` with browser headers | **HTTP 403** |
| Response title | "Just a moment..." (Cloudflare challenge) |

**Conclusion:** TopCV is protected by **Cloudflare "Just a moment..." challenge**. Plain HTTP requests are blocked. Requires either:
- Headless browser (Playwright / Selenium) with stealth plugins.
- Residential proxy + warmed browser profile.
- Cloudflare bypass service (e.g., `cloudscraper`, `scrapingbee`, `zenrows`).

### 2.3 Required Anti-Bot POC Plan (hard gate before P0 build)

| Step | Goal | Acceptance | Owner | Timebox |
|------|------|------------|-------|---------|
| 1 | Headless browser POC | `GET` TopCV search + detail returns 200 with real job content (not challenge page) | Engineering | 2 days |
| 2 | Stealth plugin validation | Same test with `playwright-stealth` / `puppeteer-extra-stealth` across 5 sessions, 0 challenge pages | Engineering | 1 day |
| 3 | Residential proxy rotation | Run 20 requests over 24h with residential proxy; <10% block rate | Engineering | 3 days |
| 4 | Cost/risk gate | If step 1–3 fails or cost >$0.05/query equivalent, drop TopCV from P0 and use VietnamWorks + ITviec only | Product | 1 day |

**Pass criteria for P0 build:** TopCV returns real HTML reliably (≥90% success) with a method whose fully-loaded cost fits the scraper budget (see §8).

**Fail criteria:** Challenge page persists, headless detection blocks, or proxy cost exceeds budget.

## 3. ITviec — Initial Recon

### 3.1 Method

- `GET https://itviec.com/it-jobs/data-engineer`
- `GET https://itviec.com/it-jobs/data-engineer-global-e-commerce-data-platform-crossian-2727`
- Parse with `lxml`.

### 3.2 Search Page Findings

| Item | Result |
|---|---|
| HTTP status | **200 OK** |
| HTML size | ~527 KB |
| Anti-bot | **None observed** (no Cloudflare challenge, no CAPTCHA) |
| Job cards selector | `//div[contains(@class,"job-card") and contains(@class,"ipt-2")]` |
| Jobs per search page | 20 cards |
| Job title | `h3/a[@class="text-it-black text-hover-red"]` |
| Job URL | `h3/a/@href` (e.g., `https://itviec.com/it-jobs/data-engineer-global-e-commerce-data-platform-crossian-2727?lab_feature=preview_jd_page`) |
| Data attributes | `data-job-key`, `data-search--job-selection-job-slug-value`, `data-search--job-selection-job-url-value` |

### 3.3 Detail Page Findings

| Item | Result |
|---|---|
| HTTP status | **200 OK** |
| HTML size | ~346 KB |
| Job title | `h1` (e.g., "Data Engineer, Global E-commerce Data Platform") |
| Company | `//a[contains(@href,"/companies/")]` hoặc text gần title |
| Salary | `Sign in to view salary` (bị ẩn nếu không đăng nhập) |
| Location | Text gần company, e.g., "Tầng 1, Tòa nhà Pax Sky..." |
| Work mode | "At office" |
| Posted time | "Posted 4 hours ago" / "Posted 1 day ago" |
| Skills | `//span[contains(@class,"skill")]` hoặc text dưới "Skills:" |
| JD | `//div[contains(@class,"jd-main")]` |

### 3.4 Confirmed Selectors (ITviec)

| Field | XPath / Selector | Notes |
|---|---|---|
| Job list cards | `//div[contains(@class,"job-card") and contains(@class,"ipt-2")]` | 20 cards/search page |
| Job title (list) | `.//h3/a/text()` | |
| Job URL (list) | `.//h3/a/@href` | Remove `?lab_feature=...` for canonical |
| Title (detail) | `//h1//text()` | |
| Company | `//div[contains(@class,"employer-name")]//text()` | |
| Location | Heuristic: text containing `phố`, `đường`, `tầng`, `tòa nhà` in `jd-main` | |
| Work mode | Heuristic: text `At office` / `Remote` / `Hybrid` | |
| Posted time | `Posted X hours ago` / `Posted X day ago` in `jd-main` | |
| Skills | `//div[contains(text(),"Skills:")]/following-sibling::*//text()` | |
| Job domain | Text after `Job Domain:` | |
| Job description | Text after `Job description` in `//div[contains(@class,"jd-main")]` | Long, needs cleanup |
| Salary | `Sign in to view salary` (hidden for non-logged-in users) | **Data quality risk** |

### 3.5 Sample Parsed Fields (ITviec)

```json
{
  "title": "Data Engineer, Global E-commerce Data Platform",
  "company": "Crossian",
  "location": "Tầng 1, Tòa nhà Pax Sky, 63-65 phố Ngô Thì Nhậm, Phường Phạm Đình Hổ, Ha Noi",
  "work_mode": "At office",
  "posted_text": "Posted 4 hours ago",
  "skills": ["Data Engineer", "AWS", "Kubernetes", "DBT", "Python", "SQL"],
  "job_domain": ["E-commerce", "Retail and Wholesale", "Transportation, Logistics and Warehouse"],
  "salary": "Sign in to view salary"
}
```

### 3.6 PII Scan (ITviec)

- 0 phone/email trong 1 sample detail page.
- Cần quét thêm 10–20 samples để xác nhận.

### 3.7 Risks

- **Salary bị ẩn** (`Sign in to view salary`) cho đa số jobs. Đây là **data quality risk** lớn cho aggregator.
- ITviec có thể thay đổi HTML structure hoặc bật Cloudflare sau khi phát hiện crawl.
- `lab_feature=preview_jd_page` query param có thể là feature thử nghiệm; cần test link canonical không param.

## 4. Comparison

| Factor | VietnamWorks | ITviec | TopCV |
|---|---|---|---|
| Access | Public API, no auth | HTML, no challenge | HTML, **Cloudflare challenge** |
| Ease | High | Medium | Low (requires anti-bot) |
| Data richness | High (salary visible) | Medium (salary hidden) | Unknown (blocked) |
| Rate limit risk | Low in short test | Medium | Unknown |
| Anti-bot cost | None | None | Residential proxy / headless / bypass service |
| **P0 recommendation** | **Build** | **Build** | **POC first** |

## 5. Preliminary Recommendations

### ITviec

**Proceed with HTML scraper** but address:
- Salary hidden issue: parse `prettySalary` / salary range if sign-in not required; otherwise mark `salary` as `null` with `confidence=low` and flag `salary_hidden=true`.
- If >50% of sampled detail pages hide salary, downgrade salary from P0 field to P1 enrichment and rely on VietnamWorks/TopCV (if TopCV POC passes) for salary data.
- Implement golden fixture tests for selectors and add DOM-change alert.
- Add PII redaction (FR-47 / AD-25).

### TopCV

**Do not proceed to P0 build until anti-bot POC passes.** Required:
- Headless browser test (Playwright with `playwright-stealth` or `puppeteer-extra-stealth`).
- If headless fails, evaluate scraping service or residential proxy.
- If cost >$0.05/query equivalent, consider dropping TopCV from P0.

## 6. Go/No-Go for TopCV/ITviec in P0

**GO if:**
- ITviec scraper can reliably extract title, company, location, skills, JD from 10+ test pages.
- TopCV anti-bot POC passes (headless or bypass service) and cost is acceptable.
- ToS for both allows scraping.

**NO-GO if:**
- TopCV cannot be bypassed within budget.
- ITviec salary data is almost entirely hidden and degrades value.
- ToS prohibits scraping either source.

## 8. Scraper Budget Gate (P0)

To avoid exceeding the 30–50 built-in scraper cap and keep cost predictable:

- VietnamWorks (public API) and ITviec (HTML) each count as **1 built-in scraper** toward the cap.
- TopCV counts as **1 built-in scraper only if the anti-bot POC passes and the fully-loaded cost (proxy/headless/bypass service) is ≤$0.05/query equivalent**.
- If TopCV fails the cost gate, it is **deferred or delegated to an OAuth/connector model** rather than a built-in scraper.
- Total new HR vertical scrapers added in P0: **2–3**, depending on TopCV POC outcome.

## 7. Status

- **Planned:** 2026-08-05
- **Execution:** 2026-08-05
- **Updated:** 2026-08-10 — added TopCV anti-bot POC hard gate, ITviec salary strategy, and scraper budget gate.
- **Report:** 2026-08-05
