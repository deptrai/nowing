# Story 21.12: Viral Social Outbound Co-pilot (Voice Learner & Outlier Analyzer)

Status: ready-for-dev

<!-- Note: Governed by architecture-xactions-social-integration-2026-08-15 (AD-SOC-1 to AD-SOC-7), AD-11 (Memory), AD-25 (PII Redaction), AD-31 (Tenant Isolation), and UX Contract ux-contract-workspace-mode-switch.md -->

## Story

As a founder, real estate influencer, or B2B marketer,
I want an AI co-pilot that analyzes high-performing outlier viral posts in my niche across Facebook, X, and TikTok, learns my unique writing voice from writing samples/profiles, and rewrites proven viral structures into original lead-magnet post drafts,
So that I can build a compounding inbound lead generation engine alongside outbound prospecting while maintaining authentic brand voice, platform formatting constraints, and full editorial control.

---

## Acceptance Criteria

### 1. Voice Profile Learning & Multi-Persona Knowledge Base Persistence
- **Given** a user's writing sample (text input $\ge 100$ words) or social profile handle/post URLs in `Content Mode`,
- **When** `VoiceProfileLearner.extract_voice_profile(sample_text, profile_name, platform)` executes,
- **Then** it validates `min_words=100` (returning `HTTP 422 Unprocessable Entity` if input is insufficient), analyzes tone (e.g. authoritative, conversational, contrarian), average sentence length, paragraph cadence, hook patterns, vocabulary preferences, and formatting quirks (emoji density, bullet points, line break style) using structured JSON output (`response_format={"type": "json_object"}`),
- **And** it persists the `VoiceProfile` payload into the Knowledge Base as a `Memory` record (`type = "semantic"`, `tags = ["voice_profile", "social_copilot"]`, `source_type = "manual"`, `workspace_id`, `client_id`) with fields `profile_name`, `is_active: bool`, and metadata in `source_input`, returning the active `profile_id`.

### 2. Viral Outlier Identification, Zero-Division Safety & Redis Caching
- **Given** target industry niche keywords or monitored group/account feeds from XActions (`social_posts`),
- **When** `ViralPostAnalyzer.find_outliers(target_keywords, min_multiplier=3.0, min_engagement=10)` runs,
- **Then** it calculates the author baseline engagement score ($\text{Engagement} = \text{Reactions} + 2 \times \text{Comments} + 3 \times \text{Shares}$) with zero-division protection ($\text{Baseline} = \max(\text{Baseline}_{\text{author}}, 1.0)$), caching the baseline in Redis (`cache:social:baseline:{platform}:{author_id}`, TTL: 3600s),
- **And** it filters for outlier posts where $\text{Score} \ge \max(10, 3.0 \times \text{Baseline})$ (or top 5th percentile within the niche dataset), returning structured metadata (`platform`, `external_post_id`, `engagement_score`, `baseline_ratio`, `content`, `published_at`).

### 3. PII-Sanitized Viral Mechanics Deconstruction & 4-Tier Hook Taxonomy
- **Given** an identified outlier viral post,
- **When** `ViralPostAnalyzer.deconstruct_viral_mechanics()` processes the post,
- **Then** it passes the text through `app/services/pii/redact.py` (`context="social_template"`) to strip personal phone numbers and emails (per AD-25),
- **And** it breaks down the post into 4 core Structural Elements:
  1. `hook`: First 1-2 lines (the thumb-stopper)
  2. `re_hook / tension`: Context expansion or problem intensification
  3. `body / value delivery`: Core actionable insights, list, or narrative turn
  4. `call_to_action / engagement_prompt`: Lead magnet offer, comment trigger, or discussion prompt
- **And** it categorizes the primary hook pattern into standardized taxonomies:
  - `contrarian_hook`: Disruptive opening defying common industry wisdom
  - `story_shift`: Personal before-and-after transformation narrative
  - `value_list`: High-density curation or step-by-step actionable framework
  - `data_reveal`: Surprising industry statistic, ROI metric, or case study breakdown.

### 4. Multi-Platform Voice-Matched Rewrite Engine & Draft Variation Generator
- **Given** a deconstructed viral post template, an active `VoiceProfile`, and target platform (`target_platform: "twitter" | "facebook" | "linkedin" | "threads"`),
- **When** `ViralDraftGenerator.generate_drafts(template_id, topic, voice_profile_id, target_platform, n_variations=3)` is invoked,
- **Then** it uses specialized few-shot prompt templates for the classified hook taxonomy, enforcing platform constraints (Twitter: $\le 280$ chars or long-form thread; Facebook/LinkedIn: structured paragraph breaks and hook formatting),
- **And** it generates $N=3$ distinct draft variations matching the user's tone and vocabulary, tagged with angle metadata (`angle: "contrarian" | "framework" | "case_study"`), estimated reading time, and lead-magnet CTA placeholders,
- **And** it records token consumption to `TokenUsage` and logs a `BillingEvent` (`usage_type = "social_copilot_generation"`).

### 5. Multi-Platform Graceful Degradation & Manual Ingestion Fallback
- **Given** unsupported social platforms (e.g. TikTok) or temporary upstream scraping network timeouts,
- **When** querying feeds,
- **Then** the service returns `degraded=True` with a clear explanation without crashing the API, and provides a manual URL/text paste endpoint `POST /api/workspaces/{id}/social-copilot/manual-ingest` allowing users to analyze any pasted post directly.

### 6. Human-in-the-Loop Editorial Review & 1-Click Copy UI (`Content Mode`)
- **Given** generated post draft variations,
- **When** displayed in the Nowing Web `Content Mode` (`/dashboard/[workspace_id]/content/social-copilot`),
- **Then** the interface renders a split review layout:
  - Left panel: Original viral post reference (PII redacted), breakdown of "Why it worked", hook taxonomy badge, and engagement multiplier
  - Right panel: Interactive draft editor with tabbed variations (A/B/C), live Markdown preview toggle, real-time character/word counters, platform length warning indicators, and 1-click `Copy to Clipboard` with visual confirmation toast,
- **And** AI **never** automatically posts to the user's personal social accounts (strictly human-in-the-loop editorial guardrail).

### 7. AI Agent Tools & Capability Registration
- **Given** an interactive chat or automation agent session,
- **When** querying available tools,
- **Then** capabilities `social.learn_voice`, `social.analyze_viral_outliers`, and `social.generate_viral_drafts` are registered in `CapabilityRegistry` with input/output Pydantic schemas, progress telemetry, and billing units (`BillingUnit.SOCIAL_LEAD_ITEM` / `TokenUsage`).

---

## Tasks / Subtasks

- [ ] Task 1: Voice Profile Schemas, Learning Engine & Memory Storage (AC: 1)
  - [ ] 1.1 Tạo schemas `VoiceProfile`, `VoiceAnalysisRequest`, `VoiceProfileResponse`, `VoiceProfileListItem` tại `nowing_backend/app/schemas/voice_profile.py`.
  - [ ] 1.2 Viết validation `min_words=100` trong Pydantic schema và endpoint handler.
  - [ ] 1.3 Xây dựng `VoiceProfileLearner` tại `nowing_backend/app/services/social_copilot/voice_learner.py` với structured JSON prompt (`response_format={"type": "json_object"}`) trích xuất tone, cadence, vocabulary, hook preferences, formatting style.
  - [ ] 1.4 Tích hợp lưu trữ `VoiceProfile` vào bảng `memories` (`type=MemoryType.SEMANTIC`, `tags=["voice_profile"]`, `workspace_id`, `client_id`, `profile_name`, `is_active`) qua `MemoryService`.
  - [ ] 1.5 Thêm REST endpoints tại `nowing_backend/app/routes/social_copilot_routes.py` (`POST /api/workspaces/{id}/voice-profiles`, `GET /api/workspaces/{id}/voice-profiles`, `PUT /api/workspaces/{id}/voice-profiles/{profile_id}/activate`).

- [ ] Task 2: Viral Outlier Detection, Baseline Scoring & Redis Caching (AC: 2, 5)
  - [ ] 2.1 Xây dựng `OutlierDetector` tại `nowing_backend/app/services/social_copilot/outlier_detector.py`.
  - [ ] 2.2 Viết query SQLAlchemy tính toán median/mean engagement ($\text{reactions} + 2\times\text{comments} + 3\times\text{shares}$) theo từng tác giả trong `social_posts`.
  - [ ] 2.3 Áp dụng Zero-division guard $\text{Baseline} = \max(\text{Baseline}_{\text{author}}, 1.0)$ và điều kiện lọc $\text{Score} \ge \max(10, 3.0 \times \text{Baseline})$.
  - [ ] 2.4 Tích hợp Redis Caching cho author baseline (`cache:social:baseline:{platform}:{author_id}`, TTL: 3600s).
  - [ ] 2.5 Xây dựng fallback handler `POST /api/workspaces/{id}/social-copilot/manual-ingest` cho phép phân tích URL/text dán thủ công khi scraper degrade.

- [ ] Task 3: PII Redaction & 4-Tier Hook Taxonomy Deconstruction (AC: 3)
  - [ ] 3.1 Xây dựng `ViralMechanicsDeconstructor` tại `nowing_backend/app/services/social_copilot/mechanics_deconstructor.py`.
  - [ ] 3.2 Tích hợp sanitization qua `app/services/pii/redact.py` (`context="social_template"`) gỡ bỏ SĐT, email nhạy cảm trước khi xử lý.
  - [ ] 3.3 Bóc tách 4 thành phần bài viết (`hook`, `re_hook`, `body`, `cta`) và phân loại Hook Taxonomy (`contrarian_hook`, `story_shift`, `value_list`, `data_reveal`) kèm lý giải "Why it worked".

- [ ] Task 4: Multi-Platform Voice-Matched Rewrite Engine & Few-Shot Library (AC: 4)
  - [ ] 4.1 Xây dựng `ViralDraftGenerator` tại `nowing_backend/app/services/social_copilot/draft_generator.py`.
  - [ ] 4.2 Thiết lập thư viện Few-Shot prompt templates theo từng Hook Taxonomy và từng nền tảng (`twitter`, `facebook`, `linkedin`).
  - [ ] 4.3 Sinh 3 biến thể A/B/C với góc tiếp cận đa dạng (tranh biện, case study, checklist giá trị) và kiểm soát độ dài ký tự theo nền tảng đích.
  - [ ] 4.4 Metering: Ghi nhận `TokenUsage` và `BillingEvent` (`usage_type = "social_copilot_generation"`).

- [ ] Task 5: AI Capabilities & Agent Tools Registration (AC: 7)
  - [ ] 5.1 Đăng ký Capability `social.learn_voice` tại `nowing_backend/app/capabilities/social/learn_voice/`.
  - [ ] 5.2 Đăng ký Capability `social.analyze_viral_outliers` tại `nowing_backend/app/capabilities/social/analyze_viral_outliers/`.
  - [ ] 5.3 Đăng ký Capability `social.generate_viral_drafts` tại `nowing_backend/app/capabilities/social/generate_viral_drafts/`.
  - [ ] 5.4 Đăng ký Agent Tools tương ứng trong `app/capabilities/core/access/agent.py` để Main Agent có thể gọi trực tiếp trong chat.
  - [ ] 5.5 Đăng ký `social_copilot_routes` trong `app/app.py`.

- [ ] Task 6: Frontend Content Mode UI & Split-View Post Editor (AC: 6)
  - [ ] 6.1 Khởi tạo route `/dashboard/[workspace_id]/content/social-copilot/page.tsx` trong `nowing_web`.
  - [ ] 6.2 Xây dựng component `VoiceProfileManager` (quản lý danh sách personas, form học giọng văn mới kèm word counter $\ge 100$ từ).
  - [ ] 6.3 Xây dựng component `OutlierFeedViewer` (danh sách bài viral, badge $\ge 3\times$, taxonomy tag, manual URL import modal).
  - [ ] 6.4 Xây dựng component `ViralDraftReviewPanel` (Split layout: Gốc vs Biến thể A/B/C, Markdown Live Preview toggle, Character/Word counter, 1-Click Copy Toast feedback).
  - [ ] 6.5 Viết API client tại `nowing_web/lib/apis/social-copilot-api.service.ts`.

- [ ] Task 7: Unit & Integration Tests (AC: 1-7)
  - [ ] 7.1 `tests/unit/services/social_copilot/test_voice_learner.py` (Validation $\ge 100$ từ, JSON output parsing, trích xuất tone/cadence).
  - [ ] 7.2 `tests/unit/services/social_copilot/test_outlier_detector.py` (Tính baseline, zero-division guard, ngưỡng $\ge 3\times$, Redis cache hit/miss).
  - [ ] 7.3 `tests/unit/services/social_copilot/test_mechanics_deconstructor.py` (PII redaction, phân loại taxonomy, 4 structural parts).
  - [ ] 7.4 `tests/unit/services/social_copilot/test_draft_generator.py` (Giới hạn ký tự nền tảng Twitter/Facebook, tích hợp voice profile).
  - [ ] 7.5 `tests/integration/routes/test_social_copilot_routes.py` (Multi-persona persistence trong `memories`, tenant isolation `client_id`/`workspace_id`).
  - [ ] 7.6 Frontend typecheck (`pnpm tsc --noEmit`) & Biome linter check.

---

## Dev Notes

### Architecture Invariants & Guardrails
- **Zero-Reinvention XActions Integration (AD-SOC-1):** Tận dụng dữ liệu mạng xã hội đã thu thập từ `social_posts` và `XActionsSocialAdapter` (Facebook, Twitter/X).
- **First-Class Memory Storage (AD-11 / AD-35):** Lưu trữ hồ sơ giọng văn `VoiceProfile` trực tiếp trong bảng `memories` với `type = MemoryType.SEMANTIC` và `tags = ["voice_profile"]`. Không tạo bảng vector riêng biệt.
- **PII Compliance & Sanitization (AD-25):** Mọi nội dung bài đăng mẫu từ mạng xã hội phải được chạy qua `app/services/pii/redact.py` (`context="social_template"`) trước khi hiển thị hoặc đưa vào context sinh bài.
- **Tenant Isolation (AD-31):** Mọi truy vấn `social_posts`, `memories`, và `voice_profiles` bắt buộc lọc theo `workspace_id` và `client_id`.
- **Human-in-the-Loop Safety Invariant:** Tuyệt đối không tự động đăng bài lên tài khoản cá nhân của người dùng. Hệ thống chỉ đóng vai trò phân tích, tạo bản thảo, và cung cấp nút Sao chép (Copy) / Tải về (Export).
- **Outlier Formula & Zero-Division Invariant:**
  $$\text{Score} = \text{Reactions} + 2 \times \text{Comments} + 3 \times \text{Shares}$$
  $$\text{Outlier Condition} = (\text{Score} \ge 10) \land \left(\frac{\text{Score}}{\max(\text{Baseline}_{\text{author}}, 1.0)} \ge 3.0\right)$$

### Deterministic Test Fixtures (for Dev Agent)

```python
# Fixture 1: Contrarian Hook Post
SAMPLE_CONTRARIAN_POST = """
Hầu hết các môi giới BĐS đang đốt tiền vô ích vào Facebook Ads.
Thực tế 90% giao dịch phân khúc cao cấp năm nay đến từ mạng lưới quan hệ ngầm và định vị cá nhân qua nội dung chuyên sâu.
Dưới đây là quy trình 3 bước tôi dùng để chốt 4 căn biệt thự mà không tốn 1 đồng quảng cáo:
1. Xác định tệp khách hàng mua kín qua dữ liệu đăng ký doanh nghiệp
2. Viết bài phân tích dòng tiền chuyên sâu thay vì đăng tin bán nhà rác
3. Tiếp cận riêng tư qua tin nhắn trực tiếp kèm báo cáo định giá độc quyền
Comment 'BÁO CÁO' để nhận file phân tích dòng tiền mẫu.
"""

# Fixture 2: Voice Profile JSON Output Shape
SAMPLE_VOICE_PROFILE_JSON = {
    "profile_name": "Real Estate Founder",
    "tone": "authoritative, pragmatic, direct",
    "average_sentence_length": 14,
    "paragraph_cadence": "short paragraphs, 1-2 sentences per line, high whitespace",
    "hook_preference": "contrarian opening with specific numbers",
    "vocabulary": ["dòng tiền", "phân khúc cao cấp", "định vị", "thực chiến", "tệp khách"],
    "formatting_quirks": {
        "emoji_density": "low",
        "bullet_style": "numbered_list",
        "line_break_frequency": "high"
    }
}
```

### Source Tree Components to Touch / Create

#### Backend (`nowing_backend/`)
- `[NEW]` `app/schemas/voice_profile.py`: Pydantic models cho Voice Profile, Hook Taxonomy, và Draft Variations.
- `[NEW]` `app/services/social_copilot/voice_learner.py`: Service phân tích mẫu văn bản và trích xuất giọng văn.
- `[NEW]` `app/services/social_copilot/outlier_detector.py`: Thuật toán tính baseline, zero-division guard, và Redis caching.
- `[NEW]` `app/services/social_copilot/mechanics_deconstructor.py`: Phân tích 4 thành phần bài viết, PII sanitization, và phân loại Hook Taxonomy.
- `[NEW]` `app/services/social_copilot/draft_generator.py`: Prompt orchestrator sinh 3 biến thể nội dung theo platform constraints.
- `[NEW]` `app/routes/social_copilot_routes.py`: REST API endpoints cho Voice Profile, Outliers, Manual Ingest, và Draft Generation.
- `[NEW]` `app/capabilities/social/learn_voice/`: Capability định nghĩa và executor cho Voice Learning.
- `[NEW]` `app/capabilities/social/analyze_viral_outliers/`: Capability định nghĩa và executor cho Outlier Detection.
- `[NEW]` `app/capabilities/social/generate_viral_drafts/`: Capability định nghĩa và executor cho Draft Rewriting.
- `[MODIFY]` `app/app.py`: Đăng ký `social_copilot_routes` router.
- `[MODIFY]` `app/capabilities/core/access/agent.py`: Đăng ký Agent Tools cho Social Co-pilot.

#### Frontend (`nowing_web/`)
- `[NEW]` `app/dashboard/[workspace_id]/content/social-copilot/page.tsx`: Main page cho Viral Social Co-pilot.
- `[NEW]` `components/social-copilot/VoiceProfileManager.tsx`: Form quản lý & học giọng văn người dùng (multi-persona).
- `[NEW]` `components/social-copilot/OutlierPostCard.tsx`: Card hiển thị bài viral, hệ số baseline, PII-redacted text, và hook badge.
- `[NEW]` `components/social-copilot/ViralDraftReviewPanel.tsx`: Split view so sánh bài gốc và 3 biến thể A/B/C, Markdown Preview, Character Counter, 1-Click Copy Toast.
- `[NEW]` `lib/apis/social-copilot-api.service.ts`: Client API service gọi backend endpoints.

### ATDD Artifacts
- **Checklist:** `_bmad-output/test-artifacts/atdd-checklist-21-12-viral-social-co-pilot.md`
- **Unit tests:**
  - `nowing_backend/tests/unit/services/social_copilot/test_voice_learner.py`
  - `nowing_backend/tests/unit/services/social_copilot/test_outlier_detector.py`
  - `nowing_backend/tests/unit/services/social_copilot/test_mechanics_deconstructor.py`
  - `nowing_backend/tests/unit/services/social_copilot/test_draft_generator.py`
- **Integration tests:** `nowing_backend/tests/integration/routes/test_social_copilot_routes.py`
- **E2E tests:** `nowing_web/tests/content/social-copilot.spec.ts`

### References
- [Architecture Spine: architecture-xactions-social-integration-2026-08-15/ARCHITECTURE-SPINE.md] (AD-SOC-1, AD-SOC-6)
- [PII Redaction Architecture: app/services/pii/redact.py] (AD-25 Data Privacy)
- [UX Contract: ux-contract-workspace-mode-switch.md#N2.4] (Content Mode navigation & surfaces)
- [Epics Document: epics.md#Story 21.12] (FR-82 Viral Social Outbound Co-pilot)
- [Memory Architecture: app/services/memory/service.py] (AD-11 First-Class Memory Persistence)

---

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash

### Debug Log References

### Completion Notes List
- Ultimate context engine analysis and full checklist validation completed.
- BDD Acceptance Criteria strictly aligned with Epics FR-82, AD-SOC-1/6, AD-11 (Memory), AD-25 (PII Redaction), and AD-31 (Tenant Isolation).
- Zero-division safety, Redis baseline caching, and min_words validation explicitly codified.
- Multi-persona voice profile support, platform formatting limits, and 4-tier hook taxonomy few-shot library incorporated.
- Human-in-the-loop editorial guardrails locked (never auto-post, copy-to-clipboard UI).

### File List
- `_bmad-output/implementation-artifacts/21-12-viral-social-co-pilot.md`
