# Sprint Change Proposal — Customer Location Profile & Pre-Flight Lead Plan

**Date:** 2026-08-29  
**Project:** Nowing  
**Raised by:** User during Sales Copilot E2E verification & Lead Radar benchmark  
**Skill:** `bmad-correct-course` (Batch review)  

---

## Section 1: Issue Summary

### 1.1 Trigger
Trong quá trình chạy thử end-to-end (E2E) Sales Copilot Playbook Builder, user quan sát giao diện của **Lead Radar by Better Work** (`lead.betterwork.id.vn`) qua ảnh chụp màn hình và nhận xét:

> "Họ làm khá kỹ phần phân tích vị trí khách hàng ban đầu. Đây là điều mà Nowing chưa làm tốt, nên leads ra nhiều khi không đúng ý."

User yêu cầu phân tích kỹ flow thu thập dữ liệu của Lead Radar, xem lại toàn bộ flow AI gen lead của Nowing, rồi đề xuất giải pháp cải tiến tổng thể.

### 1.2 Evidence from Lead Radar (Image #10, #11, #12)
Lead Radar là giải pháp **Lead Radar v2.4** — "Hạ tầng khai thác dữ liệu khách hàng cấp doanh nghiệp". Các điểm nổi bật quan sát được:

- **Dashboard "Trạng thái quét"**
  - Worker quét 24/7
  - Toggle "Quét toàn hệ thống"
  - Metrics: `Nguồn đang hoạt động 0/0`, `Proxy khoẻ 1/1`, `Lead hôm nay 0`
  - **Trạng thái theo nền tảng**: cards cho Facebook, Threads, LinkedIn, Google Maps
  - Mỗi card: trạng thái hoạt động, heartbeat, concurrency, on/off toggle

- **Wizard lập kế hoạch thu thập dữ liệu**
  - Step-by-step form
  - Phân tích vị trí khách hàng rất kỹ: tỉnh/thành → quận/huyện → phường/xã
  - Có bản đồ / radius
  - Chọn nguồn, từ khóa, hành vi, mục tiêu
  - Tóm tắt kế hoạch trước khi launch

### 1.3 Evidence from Nowing Current State

#### 1.3.1 Quickstart Playbook Builder (`nowing_web/components/assistant-ui/quickstart-playbook-builder.tsx`)
- 5 bước wizard: Preset → Intent → Location → Product → Channels → Preview
- `location` là `<Input>` text đơn giản
- Không có:
  - Dropdown tỉnh/thành/quận/huyện/phường/xã
  - Bản đồ / radius
  - Phân biệt "khách hàng ở đâu" vs "giao dịch ở đâu"
  - Tóm tắt kế hoạch thu thập trước khi chạy
  - Dashboard trạng thái nguồn

#### 1.3.2 Lead Gen Orchestrator (`nowing_backend/app/lead_intelligence/services/lead_gen_orhestrator.py`)
- Nhận `query`, `filters`, `campaign_spec`
- `ICPCriteria.target_locations` là `list[str]` text
- Không có geocode, radius, province/district/ward code
- `resolve_adapters_for_campaign` chọn adapter theo keyword, không tận dụng vị trí để ưu tiên nguồn
- `pre_filter_by_icp` chưa xem xét location radius hay location type

#### 1.3.3 CampaignSpec / ICPCriteria (`nowing_backend/app/lead_intelligence/campaign/schemas.py`)
- `ICPCriteria` chỉ có `target_locations: list[str]`
- Không có:
  - `location_type` (customer residence / work / transaction / both)
  - `province_codes`, `district_codes`, `ward_codes`
  - `geo_center`, `radius_km`
  - `location_weight` trong `weights`

### 1.4 Core Problem

**"Leads ra nhiều khi không đúng ý"** vì:
1. User nhập vị trí dạng text mơ hồ (e.g. "Hà Nội").
2. Hệ thống không phân biệt khách hàng **ở** Hà Nội, **làm việc** ở Hà Nội, hay **giao dịch** ở Hà Nội.
3. Hệ thống không ưu tiên nguồn dữ liệu tốt ở khu vực đó (e.g. Batdongsan tốt ở HN, Chợ Tốt tốt ở SG).
4. Không có **pre-flight plan summary** để user duyệt trước khi tốn credit.
5. Không có **smoke test feedback loop** để tinh chỉnh vị trí sau 5 leads mẫu.

---

## Section 2: Impact Analysis

### 2.1 Epic Impact

| Epic | Impact | Required Change |
|---|---|---|
| **Epic 21 — Lead Gen Intelligence** | Cao | Mở rộng `ICPCriteria` + `CampaignSpec`; thêm `LocationProfile`; cập nhật `LeadGenOrchestrator.pre_filter_by_icp` và adapter routing. |
| **Epic 24 — Lead Conversion / Marketplace** | Trung bình | Cập nhật Quickstart Playbook Builder UI; thêm pre-flight plan summary; có thể thêm source status dashboard. |
| **Epic 10 — Scraper Expansion** | Trung bình | Mỗi adapter cần khai báo `supported_provinces` / `coverage_quality_by_location`. |
| **Epic 6 — Automations** | Thấp–Trung bình | Nếu playbook được lưu, `LocationProfile` cần serialize vào `AutomationDefinition.inputs.schema`. |
| **Epic 7 / 21-16 — UI/UX** | Cao | Thêm location selector, bản đồ preview, plan summary, source status dashboard. |

### 2.2 Story Impact

Cần thêm hoặc cập nhật stories:

- **Story 21.25 (NEW)**: Customer Location Profile in Sales Copilot Wizard.
- **Story 21.26 (NEW)**: Location-Aware Adapter Routing & Pre-Filtering.
- **Story 21.27 (NEW)**: Pre-Flight Lead Generation Plan Summary.
- **Story 24.5.x (EXTEND)**: Update Quickstart Playbook Builder UX.
- **Story 10.x (EXTEND)**: Adapter location coverage metadata.

### 2.3 Artifact Conflicts

| Artifact | Conflict / Gap | Action Needed |
|---|---|---|
| **PRD §4.10** | Không định nghĩa customer location profiling, location-aware routing, plan summary | Bổ sung FR-69.2 .. FR-69.4 |
| **Epics.md 21.15 / 21.20** | `CampaignSpec` hiện chỉ có `target_locations: list[str]` | Cập nhật AC, thêm `LocationProfile` |
| **Architecture Spine** | Chưa có quy chuẩn về geocoding, location normalization, adapter coverage | AD mới hoặc cập nhật AD-19.1 |
| **UX wireframes** | Không có location selector chi tiết, pre-flight summary, source dashboard | Bổ sung UX |
| **DB schema** | `CampaignSpec` không persist; `icp_criteria` JSONB có thể lưu `LocationProfile` mà không cần migration nếu dùng JSONB | Nếu tách `LocationProfile` thành bảng riêng cần migration |

### 2.4 Technical Impact

- **Backend**:
  - `campaign/schemas.py`: thêm `LocationProfile` và `LocationType`
  - `lead_gen_orchestrator.py`: mở rộng `pre_filter_by_icp`, adapter routing
  - `adapters/base.py`: thêm metadata `supported_provinces`, `coverage_quality_by_location`
  - `adapters/registry.py`: `resolve_adapters_for_campaign` ưu tiên adapter theo location
  - API mới: `/api/v1/vietnam-locations` (tree tỉnh/quận/phường)

- **Frontend**:
  - `quickstart-playbook-builder.tsx`: thêm step location profile, bản đồ preview, plan summary
  - Component mới: `LocationSelector`, `PlanSummaryCard`, `SourceCoverageBadge`
  - Trang mới (tùy chọn): `/dashboard/[workspace_id]/lead-sources`

- **Data**:
  - Cần dữ liệu địa lý VN: tỉnh (63), quận/huyện (~700), phường/xã (~11,000)
  - Có thể hard-code JSON hoặc seed từ GADM/OpenStreetMap
  - Geocoding: OpenStreetMap Nominatim (free, rate-limited) hoặc Google Maps (paid)

---

## Section 3: Recommended Approach

### 3.1 Option Evaluation

| Option | Viability | Notes |
|---|---|---|
| **1. Direct Adjustment** | Viable | Mở rộng wizard + schema + orchestrator filter. Phù hợp với kiến trúc hiện tại. |
| **2. Rollback** | Not viable | Không có gì cần revert. |
| **3. MVP Review** | Viable | Cần phân biệt P0 (location selector + plan summary) vs P1 (geocoding/radius/map) vs P2 (source dashboard). |

### 3.2 Recommended Path: Hybrid, Phased

- **P0 / MVP**: Customer Location Profile + Pre-Flight Plan Summary + location-aware adapter routing.
  - Location selector hỗ trợ 3 cấp (tỉnh/quận/phường) nhưng dùng **progressive disclosure**: Tỉnh/Thành bắt buộc chọn; Quận/Huyện là tùy chọn; Phường/Xã có thể thu gọn vào mục "Khu vực chi tiết (nâng cao)" để giảm friction.
  - Text-based location matching (không cần map/geocoding ở P0) với bộ từ điển alias tiếng Việt (có dấu/không dấu/viết tắt).
- **P1**: Geocoding + radius + bản đồ preview.
- **P2**: Source status dashboard tích hợp vào **Right-Canvas** (Origami split-view) thay vì trang độc lập.
- **P3**: Smoke test feedback loop (tinh chỉnh vị trí sau 5 leads).

### 3.3 Multi-Agent Review Findings (Integrated)

| Agent | Key Finding | Action in Proposal |
|---|---|---|
| **Architect (Winston)** | Dùng GSO codes; routing cần công thức tổng hợp; P0 in-memory trie + HTTP cache; P1 PostGIS | Áp dụng mã TCTK/GSO; coverage score kết hợp với vertical relevance và cost |
| **Dev (Amelia)** | Không dùng `name in text`; cần hierarchical matching (Ward → District → Province); `ICPCriteria` backward compat | Sửa `pre_filter_by_icp` dùng tokenized/Aho-Corasick lookup; thêm `model_validator` sync legacy `target_locations` |
| **UX (Sally)** | P0 chỉ Tỉnh/Thành + Quận/Huyện; dùng quick chips và smart search; PlanSummaryCard; source dashboard trong Right-Canvas | Progressive disclosure; quick chips; PlanSummaryCard; Right-Canvas source status |
| **Analyst (Mary)** | MVP tối thiểu Tỉnh/Thành + Quận/Huyện; bỏ `LocationType` cho đến khi có NLP; KPI rõ ràng | Định nghĩa KPI; `LocationType` vẫn có schema nhưng UI cho phép default "both" để giảm friction |
| **QA** | AC cần concrete; test 100+ sample với adversarial cases (Châu Thành, Quận 1/10-12, Unicode NFC) | Bổ sung adversarial test plan, hierarchical matching, Unicode normalization |

### 3.4 Model Selection / BYOK Removal for Playbooks

User feedback: playbook hiện bị lỗi validation vì model là free / Auto mode. Yêu cầu **bỏ BYOK, dùng hết global model (cho chọn model luôn)**.

**Issue:** `nowing_backend/app/automations/services/model_policy.py` chỉ cho phép automations dùng `premium global` hoặc `BYOK` models. Playbook Builder sử dụng automation flow nên bị validation block khi workspace dùng free global / Auto.

**Recommended Change (separate Story):**
- Thêm model selector trong Playbook Builder / Create Automation UI (`nowing_web/components/tool-ui/automation/create-automation.tsx` đã có UI chọn model cho automation HITL).
- Khi user tạo playbook, **snapshot model selection** vào `AutomationDefinition.models`.
- Nới lỏng policy hoặc thêm exception path cho **playbook runs** (không phải tất cả automations): cho phép chọn bất kỳ global model nào mà workspace đang active, miễn là user explicit chọn (không Auto).
- Hoặc: bỏ BYOK hoàn toàn trong context playbook → chỉ dùng global models, user chọn model từ danh sách global models.
- Cần quyết định PM/Architect: playbook nên miễn billing policy hay vẫn giữ premium-only?

### 3.5 Rationale
- P0 giải quyết **80% vấn đề** "leads không đúng ý" với chi phí thấp.
- P0 không cần dependency mới (không cần map library, geocoding service).
- Progressive disclosure giữ khả năng chi tiết tối đa nhưng giảm friction cho sales rep.
- P1/P2/P3 là những cải tiến UX/operational, có thể làm sau.

### 3.3 Rationale
- P0 giải quyết **80% vấn đề** "leads không đúng ý" với chi phí thấp.
- P0 không cần dependency mới (không cần map library, geocoding service).
- P1/P2/P3 là những cải tiến UX/operational, có thể làm sau.

---

## Section 4: Detailed Change Proposals

### 4.1 PRD Modification

**PRD §4.10 — Lead Gen Intelligence**

Thêm các FR:

```
#### FR-69.2: Customer Location Profile
As a sales rep, I want to define where my target customers live, work, and transact using structured province/district/ward selection with progressive disclosure, so that lead searches match the right geography.

Acceptance Criteria:
- Given a playbook run, when the user reaches the location step, then they select location type: customer residence, customer work, transaction location, or both (default "both").
- Given a location type, when the user selects province, then the system lists districts; when a district is selected, then the system lists wards. Phường/Xã is collapsed under an "Advanced" toggle to reduce friction.
- Given a quick-location chip (e.g. "Hà Nội", "TP.HCM"), when the user clicks it, then the system pre-fills the province and optionally nearby districts.
- Given a smart-search combobox, when the user types "Cầu Giấy", then the system suggests and tags `Hà Nội > Cầu Giấy`.
- Given a location profile, when the run executes, then the system normalizes text locations to GSO/TCTK province/district/ward codes and uses them for scoring and filtering.
- Given no location profile set, when parsing legacy campaigns, then the system syncs `target_locations` into `location_profile.location_text` for backward compatibility.

#### FR-69.3: Location-Aware Adapter Routing
As a sales rep, I want the system to prefer scrapers that have high-quality coverage in my target locations, so that I get the most relevant leads.

Acceptance Criteria:
- Given a campaign with a location profile, when adapters are resolved, then the system boosts adapters whose declared coverage includes the target provinces.
- Given two adapters in the same category, when one has better coverage in the target location, then it is executed with higher priority or larger budget share.
- Given no location match, when all adapters are available, then the system falls back to keyword-based routing.

#### FR-69.4: Pre-Flight Lead Generation Plan Summary
As a sales rep, I want to review the planned sources, locations, product, and estimated cost before the system starts scraping, so that I can adjust inputs without wasting credits.

Acceptance Criteria:
- Given a completed playbook wizard, when the user reaches the final step, then the UI displays a **PlanSummaryCard** in the playbook dialog and also in the **Right-Canvas** (Origami split-view) for persistent review: sources, location profile, intent, product, channels, estimated lead count, estimated credit cost.
- Given a source in the plan, when the user expands its coverage badge, then the system displays `supported_provinces`, `coverage_quality_by_location` (high/medium/low/none), and any degraded reasons.
- Given the plan summary, when the user confirms, then the system executes the full or smoke-test run.
- Given the plan summary, when the user clicks back, then they can edit any previous step.
- Given insufficient source coverage for the selected location, when the plan is rendered, then the system shows a warning and suggests nearby or broader locations.
```

### 4.2 Schema Changes

**File:** `nowing_backend/app/lead_intelligence/campaign/schemas.py`

```python
from typing import Literal


class LocationType(StrEnum):
    CUSTOMER_RESIDENCE = "customer_residence"
    CUSTOMER_WORK = "customer_work"
    TRANSACTION = "transaction"
    BOTH = "both"


class LocationProfile(BaseModel):
    """Structured customer location profile for targeting and scoring."""

    model_config = ConfigDict(from_attributes=True)

    location_type: LocationType = Field(
        default=LocationType.BOTH,
        description="Does the location describe where the customer lives/works or where the transaction happens?",
    )
    province_codes: list[str] = Field(default_factory=list)
    district_codes: list[str] = Field(default_factory=list)
    ward_codes: list[str] = Field(default_factory=list)
    # P1 geocoding fields
    geo_center: dict[str, float] | None = Field(
        default=None, description="{lat, lon} center for radius search"
    )
    radius_km: float | None = Field(default=None, ge=0.1, le=500.0)
    # Free-text fallback / display label
    location_text: str = Field(default="", description="Human-readable location summary")
    # Scoring weight
    location_weight: float = Field(default=0.3, ge=0.0, le=1.0)


class ICPCriteria(BaseModel):
    """Updated ICP with structured location profile."""

    model_config = ConfigDict(from_attributes=True)

    target_industries: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(
        default_factory=list,
        description="Backward-compatible free-text locations; prefer location_profile for new code.",
    )
    location_profile: LocationProfile = Field(default_factory=LocationProfile)
    target_company_sizes: list[str] = Field(default_factory=list)
    target_tech_stack: list[str] = Field(default_factory=list)
    target_categories: list[LeadSourceCategory] = Field(default_factory=list)
    target_keywords: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)
    min_fit_score: float = Field(default=0.0, ge=0.0, le=100.0)
    weights: dict[str, float] = Field(default_factory=dict)
```

### 4.3 Adapter Base Changes

**File:** `nowing_backend/app/lead_intelligence/adapters/base.py`

```python
class LeadSourceAdapter(ABC):
    """Add location coverage metadata."""

    source_name: str
    category: LeadSourceCategory = LeadSourceCategory.GENERAL
    last_execution_status: str = "ok"

    # NEW: location coverage metadata
    supported_provinces: list[str] = Field(default_factory=list)
    coverage_quality_by_location: dict[str, float] = Field(default_factory=dict)
    default_location_weight: float = 0.5
```

**Ví dụ cập nhật `BatdongsanLeadAdapter`:**

```python
class BatdongsanLeadAdapter(LeadSourceAdapter):
    source_name = "batdongsan"
    category = LeadSourceCategory.REAL_ESTATE
    supported_provinces = ["01", "79", "48", "..."]  # HN, SG, ĐN...
    coverage_quality_by_location = {"01": 0.95, "79": 0.85, "48": 0.75}
```

### 4.4 Orchestrator Changes

**File:** `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py`

#### 4.4.1 Adapter Routing by Location

Trong `resolve_adapters_for_campaign` (`registry.py`):

```python
def _location_coverage_score(adapter: LeadSourceAdapter, profile: LocationProfile) -> float:
    if not profile.province_codes:
        return 0.0
    scores = [
        adapter.coverage_quality_by_location.get(code, 0.0)
        for code in profile.province_codes
        if code in adapter.supported_provinces
    ]
    return max(scores) if scores else 0.0


def resolve_adapters_for_campaign(self, campaign_spec) -> list[LeadSourceAdapter]:
    ...
    matched = self._keyword_and_category_resolve(...)  # existing logic
    profile = campaign_spec.icp_criteria.location_profile
    if profile and profile.province_codes:
        # Sort matched adapters by location coverage, highest first
        matched.sort(
            key=lambda a: _location_coverage_score(a, profile),
            reverse=True,
        )
    return matched
```

#### 4.4.2 Pre-Filter by Location

Mở rộng `pre_filter_by_icp`:

```python
def pre_filter_by_icp(
    self,
    record: RawLeadRecord,
    icp_criteria: ICPCriteria | None,
) -> bool:
    if not icp_criteria:
        return True

    # Existing keyword / industry checks ...

    profile = icp_criteria.location_profile
    if profile and profile.province_codes:
        normalized = adapter.normalize_lead(record)
        lead_location_text = " ".join(
            filter(
                None,
                [normalized.city, normalized.address, normalized.title, record.data.get("content", "")],
            )
        ).lower()

        # Match province/district/ward codes against known names
        matched = self._location_matches_profile(lead_location_text, profile)
        if not matched:
            return False

    return True


def _location_matches_profile(self, text: str, profile: LocationProfile) -> bool:
    """Check if free-text location contains any province/district/ward in profile.

    Hierarchical match: ward match is strong; district match is medium;
    province match is acceptable when no district/ward selected.
    """
    # Normalize input: lower, strip diacritics, punctuation, NFC
    normalized = _normalize_vietnamese(text)
    # Build token trie / Aho-Corasick for fast multi-pattern matching
    if profile.ward_codes:
        for code in profile.ward_codes:
            if _has_location_token(normalized, self._location_names.get(code, [])):
                return True
    if profile.district_codes:
        for code in profile.district_codes:
            if _has_location_token(normalized, self._location_names.get(code, [])):
                return True
    if profile.province_codes:
        for code in profile.province_codes:
            if _has_location_token(normalized, self._location_names.get(code, [])):
                return True
    return False


def _normalize_vietnamese(text: str) -> str:
    """Lowercase, NFKD decompose, strip diacritics, remove punctuation."""
    import unicodedata
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = unicodedata.normalize("NFC", text)
    # remove punctuation except word chars and spaces
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _has_location_token(text: str, names: list[str]) -> bool:
    """Token-aware match: avoid substring false positives."""
    for name in names:
        pattern = r"\b" + re.escape(_normalize_vietnamese(name)) + r"\b"
        if re.search(pattern, text):
            return True
    return False
```

#### 4.4.3 Fit Score with Location Weight

Trong `normalize_lead` hoặc `score_lead`:

```python
def _apply_location_fit(
    self,
    lead: NormalizedLead,
    profile: LocationProfile,
) -> None:
    if not profile or not profile.province_codes:
        return
    match = self._location_matches_profile(...)
    location_score = 1.0 if match else 0.0
    weight = profile.location_weight
    base = lead.icp_fit_score or 0.0
    lead.icp_fit_score = base * (1 - weight) + (location_score * 100) * weight
```

### 4.5 Frontend UX Changes

**File:** `nowing_web/components/assistant-ui/quickstart-playbook-builder.tsx`

#### 4.5.1 New State

```typescript
interface LocationProfile {
  location_type: "customer_residence" | "customer_work" | "transaction" | "both";
  province_codes: string[];
  district_codes: string[];
  ward_codes: string[];
  location_text: string;
  location_weight: number;
}

const [locationProfile, setLocationProfile] = useState<LocationProfile>({
  location_type: "both",
  province_codes: [],
  district_codes: [],
  ward_codes: [],
  location_text: "",
  location_weight: 0.3,
});
```

#### 4.5.2 Step 2 — Location Profile

Thay thế `<Input>` text bằng:

```tsx
{step === 2 && (
  <div className="space-y-4">
    <Label>{tChat("playbook_location_type")}</Label>
    <div className="flex flex-wrap gap-2">
      {LOCATION_TYPES.map((lt) => (
        <Badge
          key={lt.value}
          variant={locationProfile.location_type === lt.value ? "default" : "outline"}
          onClick={() => setLocationProfile((p) => ({ ...p, location_type: lt.value }))}
        >
          {lt.label}
        </Badge>
      ))}
    </div>

    <LocationSelector
      value={locationProfile}
      onChange={setLocationProfile}
    />

    <div className="flex gap-2">
      <Button size="sm" variant="outline" className="flex-1" onClick={() => setStep(1)}>
        {tChat("playbook_back_button")}
      </Button>
      <Button size="sm" className="flex-1" onClick={() => setStep(3)}>
        {tChat("playbook_next_button")}
      </Button>
    </div>
  </div>
)}
```

#### 4.5.3 Component `LocationSelector` (Progressive Disclosure)

```tsx
// nowing_web/components/leads/LocationSelector.tsx
// Props: value, onChange
// Fetches /api/v1/vietnam-locations once
// Cascading select: Province → District → Ward
// Multi-select districts/wards
// Display selected as chips
// Quick chips: Hà Nội, TP.HCM, Đà Nẵng, Hải Phòng, Cần Thơ, …
// Smart search: user types ward/district/province name or alias
// Ward/Phường hidden behind "Khu vực chi tiết (nâng cao)" toggle
// Optional: map preview (P1)
```

**UX Rules (P0):**
- Tỉnh/Thành là required (select/combobox).
- Quận/Huyện là optional; hiển thị khi đã chọn tỉnh.
- Phường/Xã là optional; collapsed mặc định để giảm overload.
- Alias lookup hỗ trợ tên có dấu / không dấu / viết tắt / tiếng Anh phổ biến ("HCM", "Saigon", "Ha Noi" → Unicode normalized + D-accent stripping).
- Multi-select: có thể chọn nhiều quận/huyện và nhiều phường/xã.

#### 4.5.4 New Step 5 — Pre-Flight Plan Summary

Chuyển step 5 từ "Preview Prompt" thành "Plan Summary":

```tsx
{step === 5 && (
  <div className="space-y-4">
    <PlanSummaryCard
      preset={selectedPreset}
      intent={intent}
      locationProfile={locationProfile}
      product={product}
      channels={selectedChannels}
      estimatedLeads={smokeTest ? 5 : 20}
      estimatedCost="~2,400 credits"
    />

    <div className="rounded-lg border border-border/60 bg-muted/50 p-3 text-xs text-foreground leading-relaxed">
      {buildPrompt(true)}
    </div>

    <div className="flex gap-2">
      <Button size="sm" variant="outline" className="flex-1" onClick={() => setStep(4)}>
        {tChat("playbook_back_button")}
      </Button>
      <Button size="sm" variant="secondary" className="flex-1" onClick={() => run(true)}>
        {tChat("playbook_run_smoke_test")}
      </Button>
      <Button size="sm" className="flex-1" onClick={() => run(false)}>
        {tChat("playbook_run_full")}
      </Button>
    </div>
  </div>
)}
```

### 4.6 Vietnam Locations API

**File:** `nowing_backend/app/routes/vietnam_locations_routes.py`

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/vietnam-locations")

@router.get("")
async def list_vietnam_locations():
    """Return hierarchical location data for Vietnam."""
    return {
        "provinces": [...],
        "districts": {...},
        "wards": {...},
    }
```

**Data source:**
- Seed JSON file: `nowing_backend/app/data/vietnam_locations.json`
- Lấy từ GADM (free) hoặc Tổng cục Thống kê (public domain)
- Code tỉnh/thành theo ISO 3166-2:VN hoặc mã QH của Việt Nam

### 4.7 Source Status in Right-Canvas (P2 / P0 for Contextual Badges)

Thay vì trang dashboard độc lập, **P2 tích hợp source status vào Right-Canvas** (Origami split-view UX của Nowing). Trong P0, hiển thị coverage badge trong `PlanSummaryCard`.

**Right-Canvas Content (`/components/right-canvas/SourceStatusPanel.tsx` P2):**
- Toggle on/off per source.
- `last_execution_status` / heartbeat.
- `coverage_quality_by_location` cho selected `LocationProfile`.
- `leads_today` per source.
- Concurrency / rate limit status.

**Coverage Badge (P0):**
- Mỗi source trong plan summary hiển thị chip `high/medium/low/none`.
- Tooltip/expand hiển thị `supported_provinces` và lý do `degraded` nếu có.

### 4.8 Smoke Test Feedback Loop (P3)

Sau khi chạy smoke test 5 leads:
- Hiển thị preview `NowingLeadMatrix` với 5 leads
- Hỏi user: "Địa điểm có đúng không?", "Muốn thu hẹp khu vực?", "Muốn đổi nguồn?"
- Cho phép quay lại chỉnh `LocationProfile` và chạy lại

---

## Section 5: Implementation Handoff

### 5.1 Scope Classification

**Moderate.**

- P0 là moderate: thêm schema, UI, routing logic, location API.
- P1/P2/P3 là moderate-to-major nếu kéo theo map, geocoding, dashboard.

### 5.2 Recommended Handoff

| Role | Responsibility |
|---|---|
| **Product Owner / PM** | Phê duyệt P0 scope; chốt danh sách tỉnh/quận/phường; quyết định geocoding provider. |
| **Solution Architect** | Review AD cho location profile, adapter routing, location normalization. |
| **UX Designer (Sally)** | Wireframe location selector, plan summary, source dashboard. |
| **Developer agent** | Implement backend schema, API, orchestrator; frontend wizard; location data seed. |
| **QA** | Test location matching accuracy, adapter routing, plan summary rendering. |

### 5.3 Success Criteria

- [ ] `LocationProfile` được thêm vào `ICPCriteria` và `CampaignSpec`.
- [ ] `quickstart-playbook-builder.tsx` có step chọn tỉnh/quận/phường và loại vị trí.
- [ ] `resolve_adapters_for_campaign` ưu tiên adapter theo `coverage_quality_by_location`.
- [ ] `pre_filter_by_icp` lọc lead theo location profile.
- [ ] Plan summary hiển thị sources, locations, product, estimated cost trước khi chạy.
- [ ] Smoke test 5 leads preview cho phép tinh chỉnh vị trí và chạy lại.
- [ ] (P2) Source status dashboard hiển thị active sources, heartbeat, leads today.

### 5.4 Sequencing

| Sprint | Deliverable |
|---|---|
| **Sprint A (P0)** | LocationProfile schema + `vietnam-locations` API + location selector UI + plan summary + adapter routing |
| **Sprint B (P1)** | Geocoding + radius + map preview + location scoring |
| **Sprint C (P2)** | Source status dashboard |
| **Sprint D (P3)** | Smoke test feedback loop |

---

## Section 6: Checklist Summary

| Section | Status |
|---|---|
| 1. Understand Trigger and Context | [x] Done |
| 2. Epic Impact Assessment | [x] Done |
| 3. Artifact Conflict and Impact Analysis | [x] Done |
| 4. Path Forward Evaluation | [x] Done |
| 5. Sprint Change Proposal Components | [x] Done |
| 6. Final Review and Handoff | [x] Done |

---

## Appendices

### Appendix A: Lead Radar UI Patterns to Adopt

1. **Per-source status card** with on/off toggle, heartbeat, concurrency.
2. **Cascading location selector** (province → district → ward).
3. **Pre-launch plan summary** showing source list, location, keywords, estimated output.
4. **Worker 24/7 dashboard** with real-time metrics.

### Appendix B: Backward Compatibility

- `ICPCriteria.target_locations` vẫn giữ nguyên.
- `LocationProfile` default factory: nếu không set, hành vi cũ không đổi.
- Adapter routing: nếu adapter không khai báo `coverage_quality_by_location`, default score = 0.5.

### Appendix C: Open Questions

1. Dùng mã tỉnh/quận/phường nào? (ISO 3166-2:VN, mã QH của TCTK, hay internal?)
2. Geocoding provider? (OpenStreetMap Nominatim, Google Maps, Mapbox?)
3. Có cần map preview ở P0 hay để P1?
4. Có cho phép user nhập nhiều tỉnh/thành cùng lúc không?

---

*End of Sprint Change Proposal.*
