---
title: Technical Spike — VietnamWorks Public API
project: Nowing
date: 2026-08-05
author: Mary (Business Analyst) for Luisphan
status: done
---

# Technical Spike: VietnamWorks Public API

## 1. Objectives

Trước khi xây dựng `vietnamworks.scrape`, cần xác nhận:

1. API endpoint `POST https://ms.vietnamworks.com/job-search/v1.0/search` còn hoạt động không?
2. Schema response có ổn định không? Các fields quan trọng có đầy đủ không?
3. Rate limit / throttling là gì? Có block IP không?
4. Có thể lấy được bao nhiêu jobs mỗi request? Pagination hoạt động thế nào?
5. Dữ liệu có chứa PII trong `jobDescription` / `jobRequirement` không?
6. Có dấu hiệu anti-bot (CAPTCHA, WAF) không?

## 2. Hypotheses

| # | Hypothesis | How to Test | Pass Criteria |
|---|---|---|---|
| H1 | API trả 200 với no-auth POST + JSON body. | curl với payload đơn giản | 200 OK, JSON hợp lệ |
| H2 | Response chứa `jobId`, `jobTitle`, `companyName`, `workingLocations`, `salaryMin/Max`, `jobDescription`, `jobRequirement`, `yearsOfExperience`, `createdOn`, `approvedOn`, `expiredOn`, `isActive`. | Parse response | ≥90% expected fields present |
| H3 | Có thể lấy ≥50 jobs per query với pagination. | Thử pageSize / page / from | ≥50 distinct `jobId` |
| H4 | Rate limit cho phép ≥100 requests/phút. | Burst test 50 requests | Không bị block 30 phút |
| H5 | Dữ liệu lương đa số là VND monthly hoặc có `salaryCurrency` + `salaryPeriodId`. | Thống kê 100 samples | ≥80% parseable |
| H6 | Một số JD chứa phone/email/tên người (PII). | Regex scan 100 JDs | Xác định tỷ lệ PII để thiết kế redaction |

## 3. Methodology

### 3.1 Manual API Call (curl)

```bash
curl -s -X POST 'https://ms.vietnamworks.com/job-search/v1.0/search' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -H 'User-Agent: Mozilla/5.0' \
  -d '{
    "keyword": "Data Engineer",
    "locationId": 29,
    "pageSize": 50,
    "page": 1
  }' | jq .
```

**Notes:**
- `locationId` 29 is Hà Nội (tentative, will verify by calling location API if available).
- Payload format is inferred from community scrapers.
- If no-auth fails, test with minimal headers.

### 3.2 Schema Extraction Script

Use Python to:
- Call API with varying keywords and locations.
- Save response JSON to `spike-output/vietnamworks-response-<ts>.json`.
- Extract field presence and types.
- Detect PII via regex.

### 3.3 Rate Limit Test

- Send 10, 20, 50 sequential requests with 1s delay.
- Send 50 rapid requests (<100ms delay).
- Record HTTP status, response time, and any 429/403/503.

### 3.4 PII Scan

Regex patterns:
- Vietnamese phone: `(\+?84|0)[35789]\d{8}`
- Email: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`
- Heuristic names: capitalized Vietnamese words in JD that look like person names (use vncorenlp or simple regex if needed).

## 4. Expected Output

- `spike-output/vietnamworks-api-schema.json` — schema map.
- `spike-output/vietnamworks-samples.jsonl` — 100 job samples.
- `spike-output/vietnamworks-pii-scan.json` — PII detection results.
- `spike-output/vietnamworks-rate-limit-log.csv` — rate limit observations.

## 5. Go/No-Go Criteria

**Go (có thể xây `vietnamworks.scrape`):**
- API trả 200, JSON ổn định.
- Có thể lấy ≥50 jobs/query với pagination.
- Rate limit cho phép ít nhất 100 requests/ngày hoặc hơn (cho pilot).
- ToS review cho phép (tài liệu riêng).

**No-go:**
- API trả 403/451/CAPTCHA.
- Rate limit quá nghiêm ngặt (<20 requests/ngày).
- Schema thay đổi liên tục hoặc thiếu fields cần thiết.

## 6. Risks

- API thay đổi trong tương lai — cần golden fixture regression tests.
- VietnamWorks có thể chặn IP cloud — cần thử từ local, staging, và production network.
- PII tồn tại trong JD — cần redaction pipeline.

## 7. Findings

Executed on 2026-08-05 from local macOS network.

### 7.1 API Availability & Auth

- `POST https://ms.vietnamworks.com/job-search/v1.0/search` trả **200 OK** với no auth.
- Cần headers: `Content-Type: application/json`, `Accept: application/json`, `User-Agent`.
- Không cần API key, cookie, hoặc signature.

### 7.2 Pagination

- Param đúng để điều chỉnh số lượng trả về là **`hitsPerPage`**, không phải `pageSize`.
- `pageSize`, `limit` bị ignore và API trả 10 jobs mặc định.
- `hitsPerPage` test đến **100** và trả đúng số lượng.
- `page` bắt đầu từ 1.
- `meta.nbHits` là tổng số jobs; `meta.nbPages` = `ceil(nbHits / hitsPerPage)`.
- **Findings:** query "Data Engineer" có **11,457 hits**, có thể lấy 100 jobs/page.

### 7.3 Schema & Field Presence

- API trả ~89 fields mỗi job.
- Fields quan trọng đều present 100% trong 100 mẫu:
  - `jobId`, `jobTitle`, `jobUrl`, `companyName`, `companyId`, `workingLocations`
  - `salaryMin`, `salaryMax`, `salaryCurrency`, `salaryPeriodId`
  - `jobDescription`, `jobRequirement`, `jobFunction`, `yearsOfExperience`
  - `createdOn`, `approvedOn`, `expiredOn`, `isActive`, `typeWorkingId`
  - `skills`, `benefits`

### 7.4 Salary Data

- `salaryPeriodId` = 1 cho tất cả mẫu → giả định là **monthly**.
- `salaryCurrency`: **USD 66%**, **VND 34%** trong sample "Data Engineer".
- Trạng thái lương:
  - **69%** `salaryMin=0 && salaryMax=0` → "Thương lượng" (negotiable).
  - **22%** có cả min/max.
  - **9%** có `salaryMin > 0` nhưng `salaryMax=0` ("Từ X").
- `prettySalary` là chuỗi hiển thị tiếng Việt ("Thương lượng", "Từ 30tr ₫/tháng", "$ 600-700 /tháng").
- `salary` (single number) bằng `salaryMin` hoặc 0; không rõ ý nghĩa — có thể bỏ qua.

### 7.5 Location Format

- `workingLocations` là list objects:
  - `cityId`, `cityName` (EN), `cityNameVI` (VN), `districtId`, `address`, `geoLoc`.
- `locationId` / `cityId` / `locationIds` trong request không filter ở server side (nbHits không đổi).
- **Implication:** filter by location phải làm ở aggregator layer sau khi fetch tất cả pages.

### 7.6 Skills Format

- `skills` là list objects: `{skillId, skillName, skillWeight}`.
- `skillWeight` luôn 100 trong sample.

### 7.7 PII Scan

- **Regex phone** trong `jobDescription` + `jobRequirement`: **0 hits** trong 100 mẫu.
- **Regex email** trong `jobDescription` + `jobRequirement`: **0 hits** trong 100 mẫu.
- **Field `emailAddress`**: present in **0** mẫu (có thể bị suppress ở public endpoint, hoặc rare).
- **Field `contactName`**: present in **96%** mẫu (e.g., "People Department", "HR Department"). Đây là tên bộ phận, không phải cá nhân, nhưng cần audit.
- **Conclusion:** PII risk từ JD là thấp trong sample, nhưng phải implement redaction pipeline vì JD có thể chứa PII trong tương lai hoặc ở source khác.

### 7.8 Rate Limit

- **Sequential 50 requests** (~1 req/s): tất cả **200 OK**, không 429.
- **Concurrent 30 requests** burst: tất cả **200 OK**, hoàn thành trong **3.15s**.
- **Average response time:** ~1.85s per request (mạng từ VN/HK server).
- **No CAPTCHA, no WAF challenge, no 403/503 observed.**
- **Caveat:** Rate limit có thể khác ở cloud IP hoặc khi scale >100s requests/hour. Cần test từ production network.

### 7.9 Anti-bot

- Không thấy Cloudflare challenge, reCAPTCHA, hoặc redirect.
- User-Agent bình thường (Mozilla/5.0) hoạt động.
- Không thấy fingerprinting headers.

### 7.10 Sample File

- 10 sample jobs (JD redacted) lưu tại: `_bmad-output/planning-artifacts/research/technical-spike-vietnamworks-samples-2026-08-05.json`.

## 8. Preliminary Go/No-Go Recommendation

**Preliminary GO on technical feasibility**, với điều kiện:
- ToS review xác nhận cho phép automated access và commercial use.
- Re-test rate limit từ production network.
- Implement golden fixture regression tests.
- Implement PII redaction pipeline trước khi lưu memory.

**No-go trigger:**
- ToS cấm scraping.
- API contract thay đổi liên tục.

## 9. Status

- **Planned:** 2026-08-05
- **Execution:** 2026-08-05
- **Report:** 2026-08-05
