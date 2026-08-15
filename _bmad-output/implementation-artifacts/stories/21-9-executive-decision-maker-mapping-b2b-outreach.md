# Story 21.9: Executive Decision Maker Mapping & B2B Lead Outreach

Status: done

<!-- Note: Governed by architecture-linkedin-b2b-2026-08-15 (AD-LI-1 to AD-LI-7) -->

## Story

As an enterprise sales team or SaaS founder,
I want to identify C-Level executives and HR leaders of expanding companies,
So that I can initiate personalized outreach and CRM synchronization.

## Acceptance Criteria

1. **Given** a target company name and optional executive role keywords, **When** `ExecutiveDorker` or `ExecutiveSearchService` is triggered, **Then** it generates privacy-compliant Google/Bing SERP dork queries (e.g., `site:linkedin.com/in/ "{company}" ("CEO" OR "Founder" OR "HR Director" OR "CFO")`) and fetches top public leadership profiles without requiring authenticated LinkedIn scraping (AD-LI-4).
2. **Given** raw search results or SERP HTML snippets, **When** parsed by `ExecutiveParser`, **Then** executive profiles (Full Name, Title, LinkedIn URL, LinkedIn Slug, Inferred Business Email pattern `first.last@{domain}`) are extracted and stored into `company_decision_makers` table with unique constraint `(company_id, linkedin_slug)` (AD-LI-5).
3. **Given** an executive full name and company domain, **When** `EmailPatternGenerator` is called, **Then** it generates corporate email candidates (handling Vietnamese diacritics removal and common name formats), performs DNS MX record checks with timeouts/fallbacks, and returns predicted emails with confidence scores (AD-LI-7).
4. **Given** identified executives and associated buying signals (e.g. recent headcount spike from Story 12.10 or active bidding tender from Story 16.5), **When** `B2BOutreachService` or "Generate Outreach Draft" is invoked, **Then** the service drafts a highly personalized, contextual B2B sales email referencing the company's specific growth signals with clear subject line, body, and call-to-action.
5. **Given** an AI Agent session, **When** invoking `b2b_find_decision_makers(company_name, roles, domain, limit)`, **Then** the agent capability returns verified executive profiles and contact suggestions (AD-LI-6).

## Architectural Invariants Mapping

* **AD-LI-1**: Zero-Login Public Ingestion — No credentials required for LinkedIn.
* **AD-LI-2**: Proxy & Human Jitter — Exponential backoff and jitter for SERP calls.
* **AD-LI-3**: Buying Signal Linkage — Correlating headcount spikes & tender wins with outreach.
* **AD-LI-4**: Public SERP Dorking — Extracting leadership profiles via search engine index.
* **AD-LI-5**: Idempotency & Unique Constraints — `(company_id, linkedin_slug)` uniqueness.
* **AD-LI-6**: Agent Tool Registration — Expose `nowing_b2b_find_decision_makers` capability.
* **AD-LI-7**: Privacy-Safe Email Inference — Rule-based pattern matching + DNS MX validation.

## Database Schema (PostgreSQL DDL)

```sql
CREATE TABLE IF NOT EXISTS linkedin_companies (
    id BIGSERIAL PRIMARY KEY,
    company_slug VARCHAR(255) NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    website TEXT,
    industry VARCHAR(255),
    headcount_range VARCHAR(50),
    headquarters VARCHAR(255),
    active_jobs_count INT DEFAULT 0,
    decision_makers JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS linkedin_jobs (
    id BIGSERIAL PRIMARY KEY,
    job_id VARCHAR(100) NOT NULL UNIQUE,
    company_id BIGINT REFERENCES linkedin_companies(id) ON DELETE SET NULL,
    company_name VARCHAR(255) NOT NULL,
    title TEXT NOT NULL,
    location VARCHAR(255),
    workplace_type VARCHAR(50),
    seniority_level VARCHAR(50),
    employment_type VARCHAR(50),
    description_text TEXT,
    skills TEXT[],
    posted_at TIMESTAMPTZ,
    raw_entities JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS company_decision_makers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id BIGINT REFERENCES linkedin_companies(id) ON DELETE CASCADE,
    company_name VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    title VARCHAR(255),
    department VARCHAR(100),
    linkedin_url TEXT,
    linkedin_slug VARCHAR(255) NOT NULL,
    email_prediction VARCHAR(255),
    confidence_score FLOAT NOT NULL DEFAULT 0.0,
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_company_executive UNIQUE (company_id, linkedin_slug)
);

CREATE INDEX IF NOT EXISTS idx_executives_company_title ON company_decision_makers(company_name, title);
CREATE INDEX IF NOT EXISTS idx_executives_slug ON company_decision_makers(linkedin_slug);
```

## Tasks / Subtasks

- [x] Task 1: Database Schema for Decision Makers (AC: 2)
  - [x] 1.1 Tạo các model `LinkedinCompany`, `LinkedinJob`, `CompanyDecisionMaker` trong `nowing_backend/app/db.py`.
  - [x] 1.2 Thiết lập unique constraint `uq_company_executive` và indexes tối ưu.
- [x] Task 2: Privacy-Compliant SERP Dorking Engine (AC: 1, 2)
  - [x] 2.1 Xây dựng `ExecutiveDorker` và `ExecutiveParser` tại `nowing_backend/app/proprietary/platforms/linkedin/`.
  - [x] 2.2 Xây dựng hàm tạo query dorking an toàn: `build_serp_dork_query(company_name, roles, domain)`.
  - [x] 2.3 Bóc tách Tên, Chức vụ và URL profile/slug từ kết quả SERP.
- [x] Task 3: B2B Email Predictor & Pattern Matcher (AC: 3)
  - [x] 3.1 Xây dựng `EmailPatternGenerator` suy đoán email theo các định dạng phổ biến, chuẩn hóa dấu tiếng Việt.
  - [x] 3.2 Tích hợp kiểm tra MX Record DNS của domain đích với timeout và fallback.
- [x] Task 4: AI Contextual Outreach Draft Engine (AC: 4)
  - [x] 4.1 Xây dựng `B2BOutreachService` tại `nowing_backend/app/services/outreach_service.py`.
  - [x] 4.2 Tích hợp phân tích Buying Signals (Tuyển dụng, Gói thầu, Vốn đầu tư) để sinh email cá nhân hóa.
- [x] Task 5: AI Agent Capability & Tools (AC: 5)
  - [x] 5.1 Đăng ký Capability `b2b.decision_makers` trong `app/capabilities/b2b/`.
  - [x] 5.2 Định nghĩa Agent Tool `nowing_b2b_find_decision_makers` trong MCP tool catalog `app/mcp_tools.py`.
- [x] Task 6: Unit & Quality Tests (AC: 1-5)
  - [x] 6.1 `tests/unit/proprietary/platforms/linkedin/test_executive_dorker.py`.
  - [x] 6.2 `tests/unit/proprietary/platforms/linkedin/test_email_predictor.py`.
  - [x] 6.3 `tests/unit/services/test_outreach_service.py`.
  - [x] 6.4 `tests/unit/capabilities/test_b2b_decision_makers.py`.

### Review Findings

#### patch
- [x] [Review][Patch] Eliminate blocking sync DNS MX lookup in parser loop & add domain caching [`nowing_backend/app/proprietary/platforms/linkedin/executive_parser.py:124-128`, `nowing_backend/app/services/email_pattern_service.py:130-154`]
- [x] [Review][Patch] Create Alembic migration script for `company_decision_makers` table [`nowing_backend/alembic/versions/206_add_company_decision_makers.py`]
- [x] [Review][Patch] Sanitize dork query roles to prevent injection & boolean syntax errors [`nowing_backend/app/proprietary/platforms/linkedin/query_builder.py:33-46`]
- [x] [Review][Patch] Wrap `build_serp_dork_query` in error handling to prevent uncaught `ValueError` on empty sanitized names [`nowing_backend/app/proprietary/platforms/linkedin/executive_dorker.py:47-50`]
- [x] [Review][Patch] Fix first/last name inversion for Western and Vietnamese order heuristics [`nowing_backend/app/services/email_pattern_service.py:52-60`]
- [x] [Review][Patch] Support URL-encoded DuckDuckGo / redirect URLs in CSS selector & href parsing [`nowing_backend/app/proprietary/platforms/linkedin/executive_parser.py:93-98`]
- [x] [Review][Patch] Support `|`, `•` delimiters and Vietnamese prepositions ('tại', 'ở') in SERP title parsing [`nowing_backend/app/proprietary/platforms/linkedin/executive_parser.py:51-72`]
- [x] [Review][Patch] Expand title/name honorifics prefix stripping (Mr, Dr) and suffix degrees (CFA, MBA, PhD) [`nowing_backend/app/services/email_pattern_service.py:12-45`]
- [x] [Review][Patch] Unescape raw HTML entities in SERP title and snippet text [`nowing_backend/app/proprietary/platforms/linkedin/executive_parser.py:103-121`]
- [x] [Review][Patch] Fix empty parenthesis `()` in B2B outreach draft when `signal_details` is missing [`nowing_backend/app/services/outreach_service.py:78-105`]


