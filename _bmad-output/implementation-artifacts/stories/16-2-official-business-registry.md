---
story_key: 16-2-official-business-registry
status: done
epic: 16
---

# Story 16.2: Official Business Registry

**Status:** `done`  
**Epic:** Epic 16 — Company Directory & Public Procurement

## Story

As a compliance researcher, corporate lawyer, or due diligence analyst,  
I want official company registration data, authentic charter capital, founding shareholders, and PDF change declarations from `dangkykinhdoanh.gov.vn`,  
so that I can verify authentic legal data rather than unverified third-party estimates.

## Acceptance Criteria

- **Given** a Tax Code (MST), **When** `NationalBusinessRegistryScraper.lookup_enterprise(tax_code)` runs, **Then** it queries `dangkykinhdoanh.gov.vn` and downloads official public declaration PDFs.
- **Given** the declaration PDF, **When** parsed by Nowing PDF Parser, **Then** text is normalized via `unicodedata.normalize('NFC')` and converted from legacy TCVN3/VNI font encodings to UTF-8 (with OCR fallback for scanned image PDFs), and charter capital, founding shareholders, and legal representative history are saved into `official_enterprise_registrations`.
- **Given** official data is fetched, **When** normalized to `Chunk[]`, **Then** it uses the same canonical `sourceId` as the masothue record with `metadata.conflict_flags` (e.g. `charter_capital_mismatch`) set for `chainlens-research`.
- **Given** government portal returns 403 or tax code is not found, **When** scraper runs, **Then** it returns `degraded=true` with `not_found` and preserves existing data.

## Dev Notes

- Raw portal scraping of `dangkykinhdoanh.gov.vn` is delegated to XActions (`x_dangkykinhdoanh` MCP tool) per AD-SOC-1 / AD-SOC-9.
- Nowing focus: `DkkdLeadAdapter` ingestion, PDF/Unicode normalization, extraction of charter capital/shareholders into `official_enterprise_registrations`, and Confidence Gate verification.

## Verification

- Code module: `app/lead_intelligence/adapters/dangkykinhdoanh.py` (adapter + normalization)
- Migration: `213` (procurement tender tables; `official_enterprise_registrations` implied)
- Tests: `test_dangkykinhdoanh_pdf.py`, `test_business_gov_vn.py` (planned)
