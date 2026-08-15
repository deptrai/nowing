# Story 12.10: LinkedIn Public Guest Jobs & Headcount Growth Signals

Status: done

<!-- Governed by architecture-linkedin-b2b-2026-08-15 (AD-LI-1 to AD-LI-7) -->

## Story

As a B2B sales development representative or recruitment agency,
I want to ingest public LinkedIn jobs without login credentials and track 30-day headcount hiring velocity,
So that I can identify high-growth companies with active purchasing power and expansion signals.

## Acceptance Criteria

1. **Given** target company slugs or job keywords in Vietnam/global, **When** `LinkedInGuestJobScraper` executes, **Then** it queries public guest job endpoints (`https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search` and `/api/jobPosting/{id}`) with rotating residential proxies and stealth headers without requiring user credentials (AD-LI-1, AD-LI-2).
2. **Given** raw job postings, **When** persisted to PostgreSQL, **Then** jobs are stored in `linkedin_jobs` with unique constraint `job_id` and linked to `linkedin_companies` with unique constraint `company_slug` idempotently (AD-LI-5).
3. **Given** 30-day historical job posting counts, **When** `HiringVelocityCalculator` computes growth metrics, **Then** it calculates `hiring_velocity_30d` and flags companies with growth rate $\ge 20\%$ as `high_buying_intent` (AD-LI-3).
4. **Given** an AI Agent session, **When** invoking `nowing_recruitment_search_linkedin_jobs(keyword, location, min_growth_rate)`, **Then** active job postings with associated company hiring velocity metrics and growth intent flags are returned (AD-LI-6).

## Architectural Invariants Mapping

- **AD-LI-1**: Zero-Login Public Data Ingestion (`httpx` + `selectolax` on guest endpoints).
- **AD-LI-2**: Proxy & Human Jitter Rate Limiting (1.5–3.5s jitter delay, proxy rotation support).
- **AD-LI-3**: Buying Signal Correlation (Hiring Growth $\ge 20\% \implies \text{high\_buying\_intent} = \text{True}$).
- **AD-LI-5**: Idempotent Ingestion with Unique `job_id` and `company_slug`.
- **AD-LI-6**: AI Agent Tool Registration (`nowing_recruitment_search_linkedin_jobs` in `app/mcp_tools.py`).

## Tasks / Subtasks

- [x] Task 1: LinkedIn Guest Job Scraper (AC: 1, 2)
  - [x] 1.1 Xây dựng `LinkedInGuestJobScraper` tại `nowing_backend/app/proprietary/platforms/linkedin/guest_job_scraper.py`.
  - [x] 1.2 Parse dữ liệu job với `selectolax`: `job_id`, `title`, `company_name`, `company_slug`, `location`, `workplace_type`, `seniority_level`, `employment_type`, `description_text`, `skills`, `posted_at`.
  - [x] 1.3 Triển khai idempotent DB persistence helper `persist_linkedin_jobs`.
- [x] Task 2: Hiring Velocity Calculator (AC: 3)
  - [x] 2.1 Xây dựng `HiringVelocityCalculator` tại `nowing_backend/app/proprietary/platforms/linkedin/velocity_calculator.py`.
  - [x] 2.2 Tính toán `hiring_velocity_30d`, `active_jobs_count`, và gán nhãn `high_buying_intent` ($\ge 0.20$).
- [x] Task 3: AI Agent Capability & Tools (AC: 4)
  - [x] 3.1 Đăng ký Capability `recruitment.linkedin_jobs` trong `nowing_backend/app/capabilities/recruitment/linkedin_jobs/` và `app/capabilities/__init__.py`.
  - [x] 3.2 Định nghĩa Agent Tool `nowing_recruitment_search_linkedin_jobs` trong `app/mcp_tools.py`.
- [x] Task 4: Unit & Quality Tests (AC: 1-4)
  - [x] 4.1 `tests/unit/proprietary/platforms/linkedin/test_guest_job_scraper.py`.
  - [x] 4.2 `tests/unit/proprietary/platforms/linkedin/test_velocity_calculator.py`.
  - [x] 4.3 `tests/unit/capabilities/test_linkedin_jobs_capabilities.py`.

### Review Findings
- [x] [Review][Patch] Fix invalid import `from app.db import get_db` causing silent persistence failures [app/capabilities/recruitment/linkedin_jobs/executor.py:100]
- [x] [Review][Patch] Eliminate N+1 SQL query loop in `HiringVelocityCalculator.calculate_from_db` using grouped conditional aggregation [app/proprietary/platforms/linkedin/velocity_calculator.py:144]
- [x] [Review][Patch] Reuse HTTP client context in `LinkedInGuestJobScraper.search_jobs` to prevent connection churn [app/proprietary/platforms/linkedin/guest_job_scraper.py:275]
- [x] [Review][Patch] Support clean job URLs without title slug in `_JOB_ID_REGEX` [app/proprietary/platforms/linkedin/guest_job_scraper.py:37]
- [x] [Review][Patch] Unicode normalize Vietnamese company names in `_slugify` to prevent slug collapsing [app/proprietary/platforms/linkedin/guest_job_scraper.py:52]
- [x] [Review][Patch] Fix skill regex matching for non-word character keywords like C++, C#, .NET [app/proprietary/platforms/linkedin/guest_job_scraper.py:221]
- [x] [Review][Patch] Fix `min_growth_rate` filtering logic when growth rate is negative or 0 [app/capabilities/recruitment/linkedin_jobs/executor.py:78]
- [x] [Review][Patch] Update `active_jobs_count` and missing job fields on PostgreSQL upsert conflict [app/proprietary/platforms/linkedin/guest_job_scraper.py:409]
- [x] [Review][Patch] Normalize naive datetime before comparing with UTC cutoff in velocity calculation [app/proprietary/platforms/linkedin/velocity_calculator.py:106]
- [x] [Review][Patch] Add unit test coverage for `persist_to_db=True` in `test_linkedin_jobs_capabilities.py` [tests/unit/capabilities/test_linkedin_jobs_capabilities.py]

## Dev Notes

- **Zero-Login Invariant:** Tuyệt đối không yêu cầu đăng nhập tài khoản cá nhân; khai thác qua Public Guest Job Ingress API.
- **Dependencies:** `selectolax>=0.3.21`, `httpx>=0.27.0`.
- **Velocity Formula:** `hiring_velocity_30d = (jobs_last_30d - jobs_prior_30d) / max(jobs_prior_30d, 1)`. If `hiring_velocity_30d >= 0.20`, `high_buying_intent = True`.

### References
- [Architecture Spine: architecture-linkedin-b2b-2026-08-15/ARCHITECTURE-SPINE.md]

