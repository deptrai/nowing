---
story_key: 26-25-customer-location-profile-selector-with-progressive-disclosu
status: ready-for-dev
baseline_commit: ad0c6f3c1
epic: 26
story: 25
---

# Story 26.25: Customer Location Profile Selector with Progressive Disclosure

**Status:** `ready-for-dev`  
**Epic:** 26 — Lead Intelligence  
**Governed by:** FR-69.2, FR-85, AD-31, `epics.md` lines 3249–3265, `architecture-xactions-social-integration-2026-08-15`.  
**Dependencies:** `app/services/location_normalize/` (Vietnamese geo normalization), Playbook Builder.

---

## Story

As a **sales rep or broker in Vietnam**,  
I want to specify where my target customers live, work, and transact using a structured province/district/ward selector that starts simple and expands only when I need more detail,  
so that lead searches match the right geography without overwhelming me with too many fields up front.

---

## Acceptance Criteria

### AC-1 — Progressive Disclosure Hierarchy
**Given** the Playbook Builder reaches the location step or user configures lead targeting,  
**When** the user opens the `LocationSelector` component:
1. It displays a required **Province/Thành phố** combobox.
2. After a province is selected, an optional **Quận/Huyện** multi-select appears.
3. An optional **Phường/Xã** multi-select is collapsed behind a "Khu vực chi tiết (nâng cao)" toggle switch.
4. When switching to another province, districts and wards reset accordingly to prevent invalid parent-child pairings.

### AC-2 — Location Type Selector
**Given** the location configuration panel,  
**When** the user sets location targeting semantics,  
**Then** they can choose between:
- `"both"` (Default — customer residence + transaction location)
- `"customer_residence"` (Nơi cư trú khách hàng)
- `"customer_work"` (Nơi làm việc / Trụ sở công ty)
- `"transaction"` (Địa bàn diễn ra giao dịch / dự án bất động sản)

### AC-3 — Smart Search with Alias & Diacritic Normalization
**Given** a smart-search text input,  
**When** the user types free-form text with or without accents or common abbreviations (e.g. "HCM", "Saigon", "sg", "Hà Nội", "hn", "Da Nang"),  
**Then**:
- The system normalizes Unicode NFC/NFD, strips diacritics using `remove_diacritics()`,
- Suggests matching province and district codes,
- Formats selected items as compact tags/chips with quick remove (`x`) buttons.

### AC-4 — Quick-Location Chips
**Given** the top of the location selector,  
**When** rendered,  
**Then** it displays one-click quick selection chips for major economic hubs:
- `Hà Nội` (`HN`)
- `TP.HCM` (`SG`)
- `Đà Nẵng` (`DN`)
- `Hải Phòng` (`HP`)
- `Cần Thơ` (`CT`)
Clicking any chip immediately selects that province and populates the available district options.

### AC-5 — Location Profile Contract & Schema Validation
**Given** the form submission,  
**When** the user saves the location step,  
**Then**:
- If no province is selected, validation prevents proceeding with message: "Vui lòng chọn ít nhất một Tỉnh / Thành phố".
- The emitted `LocationProfile` JSON payload matches:
```json
{
  "location_type": "both",
  "province_code": "SG",
  "province_name": "TP. Hồ Chí Minh",
  "district_codes": ["760", "769"],
  "district_names": ["Quận 1", "Thành phố Thủ Đức"],
  "ward_codes": [],
  "ward_names": [],
  "location_text": "TP. Hồ Chí Minh (Quận 1, Thành phố Thủ Đức)"
}
```

### AC-6 — Test Coverage
**Given** the frontend and backend components,  
**When** test suites execute,  
**Then**:
- Unit tests verify alias resolution, diacritic normalization, and cascading hierarchy reset.
- UI component test verifies progressive disclosure behavior and chip selection.
- All tests pass with clean linter and typecheck.

---

## Tasks / Subtasks

- [ ] Vietnamese Geography Catalog & API (`nowing_backend/app/services/location_normalize/`)
  - [ ] Extend `location_normalize` with canonical GSO province/district catalog mapping or lightweight API endpoint `GET /api/v1/geo/vietnam-locations`.
  - [ ] Add unit test covering province and district hierarchy resolution in `tests/unit/services/location_normalize/`.
- [ ] Frontend Location Profile Types & Catalog (`nowing_web/`)
  - [ ] Add `LocationProfile` Zod schema and types to `contracts/types/leads.types.ts`.
  - [ ] Create Vietnamese administrative divisions catalog (`lib/geo/vietnam-divisions.ts`).
  - [ ] Implement `LocationSelector` component with progressive disclosure (`components/leads/LocationSelector.tsx`).
- [ ] Integration into Playbook Builder & Lead Search
  - [ ] Embed `LocationSelector` into Lead Discovery filter panel / Playbook wizard step.
  - [ ] Connect quick-location chips and location type selector.
- [ ] Verification & Tests
  - [ ] Unit tests for `LocationSelector` rendering and cascading logic.
  - [ ] Run `tsc --noEmit`, `biome check`, and pytest.
