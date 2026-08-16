# Sprint Change Proposal: Vietnamese i18n & Smart Geo-Locale Auto-Detection

**Date:** 2026-08-17  
**Author / Role:** Developer (AI Agent)  
**Target:** Nowing Web (`nowing_web`)  
**Scope Classification:** Minor / Direct Adjustment  

---

## 1. Issue Summary

### 1.1 Trigger & Problem Statement
Hệ thống frontend `nowing_web` hiện tại đang hỗ trợ 6 ngôn ngữ (`en`, `es`, `pt`, `hi`, `zh`, `ko`), nhưng **chưa hỗ trợ Tiếng Việt (`vi`)** mặc dù Nowing đang định vị và triển khai mạnh mẽ các vertical cốt lõi tại thị trường Việt Nam (BĐS, Tuyển dụng, Doanh nghiệp MST, Leads).

Đồng thời, trải nghiệm người dùng lần đầu truy cập (`first-time visit`) chưa có cơ chế thông minh để tự động nhận diện ngôn ngữ theo vị trí địa lý / timezone / browser language của người dùng, mà luôn mặc định hiển thị tiếng Anh (`en`).

### 1.2 User Requirements
1. **Hỗ trợ Tiếng Việt (`vi`)**:
   - Cung cấp file từ điển dịch thuật toàn diện `messages/vi.json` cho toàn bộ các màn hình và tính năng (Landing page, Auth, Dashboard, Chat, Automations, Connectors, Workspace settings, User profile, v.v.).
   - Thêm `Tiếng Việt` (`🇻🇳`) vào danh sách ngôn ngữ được hỗ trợ trong `routing.ts`, `LocaleContext.tsx`, `LanguageSwitcher.tsx`, và `SidebarUserProfile.tsx`.
2. **Tự động Detect Location / Locale lần đầu**:
   - Khi người dùng truy cập lần đầu (`localStorage.getItem("nowing-locale")` chưa tồn tại / `null`):
     - Hệ thống tự động kiểm tra `navigator.languages` / `navigator.language` và Timezone (`Intl.DateTimeFormat().resolvedOptions().timeZone` e.g., `Asia/Ho_Chi_Minh`, `Asia/Saigon`, `Asia/Hanoi`).
     - Tự động gán ngôn ngữ sang `vi` nếu phát hiện tại Việt Nam hoặc trình duyệt dùng tiếng Việt (hoặc ngôn ngữ tương ứng nếu là `es`, `zh`, `ko`, `pt`, `hi`).
     - Lưu trạng thái vào `localStorage` (`nowing-locale`) để ghi nhận đã hoàn thành initial detection.
3. **Tôn trọng quyết định của người dùng**:
   - Khi người dùng đã chủ động chuyển sang ngôn ngữ khác (hoặc đã có `nowing-locale` trong `localStorage`), hệ thống giữ nguyên lựa chọn này và **không thực hiện detect đè / override**.

---

## 2. Impact Analysis

### 2.1 Epic & Story Impact
- **Affected Epic**: `Epic 7: Multi-surface Clients` (Web UI & Localization surface).
- **New Story Added**: `Story 7.8: Vietnamese i18n & Smart Geo-Locale Auto-Detection` (`ready-for-dev`).
- **No Negative Impact on other Epics**: Thay đổi hoàn toàn nằm ở client-side web application, không làm ảnh hưởng hay thay đổi bất kỳ API backend hoặc DB schema nào.

### 2.2 Artifact Conflicts
- **PRD**: Phù hợp 100% với định hướng sản phẩm và chiến lược GTM tại Việt Nam.
- **Architecture**: Kiến trúc i18n dựa trên `next-intl` và `LocaleContext` của Next.js 16 App Router được giữ nguyên, chỉ mở rộng thêm locale type và bổ sung logic auto-detection trong `LocaleContext.tsx`.

### 2.3 Technical Impact & Code Touched
1. `nowing_web/messages/vi.json` [NEW]:
   - File JSON chứa toàn bộ bản dịch tiếng Việt chuẩn hóa, khớp 100% cấu trúc key của `messages/en.json`.
2. `nowing_web/i18n/routing.ts` [MODIFY]:
   - Thêm `"vi"` vào mảng `locales: ["en", "vi", "es", "pt", "hi", "zh", "ko"]`.
3. `nowing_web/contexts/LocaleContext.tsx` [MODIFY]:
   - Cập nhật kiểu `Locale = "en" | "vi" | "es" | "pt" | "hi" | "zh" | "ko"`.
   - Bổ sung `case "vi": return (await import("../messages/vi.json")).default`.
   - Bổ sung helper `detectInitialLocale()` kiểm tra `navigator.languages` và timezone Việt Nam (`Asia/Ho_Chi_Minh`, `Asia/Saigon`, `Asia/Hanoi`, `Asia/Bangkok`).
   - Xử lý auto-detect khi `localStorage.getItem("nowing-locale")` là `null`.
4. `nowing_web/components/LanguageSwitcher.tsx` [MODIFY]:
   - Thêm `{ code: "vi" as const, name: "Tiếng Việt", flag: "🇻🇳" }`.
5. `nowing_web/components/layout/ui/sidebar/SidebarUserProfile.tsx` [MODIFY]:
   - Thêm `{ code: "vi" as const, name: "Tiếng Việt", flag: "🇻🇳" }`.

---

## 3. Recommended Approach

- **Approach**: **Option 1: Direct Adjustment**.
- **Rationale**:
  - Đóng gói toàn bộ tính năng vào một Story độc lập `Story 7.8` trong `Epic 7`.
  - Mức độ rủi ro: **Rất thấp (Low)** — Mã nguồn thay đổi mang tính chất mở rộng (purely additive) và chỉ chạy trên client-side của `nowing_web`.
  - Ước lượng nỗ lực: **Nhỏ (Low effort)** — ~1-2 giờ triển khai và kiểm thử.

---

## 4. Detailed Change Proposals

### 4.1 New Story Specification

```markdown
### Story 7.8: Vietnamese i18n & Smart Geo-Locale Auto-Detection `[ready-for-dev]`

As a Vietnamese user or international visitor,
I want Nowing to support Vietnamese language and automatically detect my location on my first visit to present the appropriate language,
So that I can immediately experience the application in my native language without manual switching, while retaining my language preferences if I choose to change them.

**Acceptance Criteria:**
1. **Given** a user accesses Nowing with no prior `nowing-locale` in `localStorage`, **When** their browser language is Vietnamese (`vi`, `vi-VN`) OR their timezone is within Vietnam (`Asia/Ho_Chi_Minh`, `Asia/Saigon`, `Asia/Hanoi`), **Then** the application automatically selects `vi` and renders all messages in Vietnamese.
2. **Given** a first-time user from a non-Vietnamese locale with no prior preference, **When** their browser language matches a supported locale (`es`, `pt`, `hi`, `zh`, `ko`), **Then** the application auto-selects that locale; otherwise it defaults to `en`.
3. **Given** a user changes language via `LanguageSwitcher` or `SidebarUserProfile` (or has existing `nowing-locale` in `localStorage`), **When** the user revisits or refreshes the page, **Then** the application strictly retains the stored language preference without overriding it.
4. **Given** the language switcher UI in header and sidebar, **When** viewed, **Then** `🇻🇳 Tiếng Việt` is present, selectable, and dynamically switches all UI components with 0 errors.
```

---

## 5. Implementation Handoff & Next Steps

- **Scope Classification**: Minor.
- **Handoff To**: Developer Agent.
- **Success Criteria**:
  1. `pnpm tsc --noEmit` và `pnpm exec biome check` trong `nowing_web/` chạy 100% sạch (0 errors).
  2. Tạo mới `nowing_web/messages/vi.json` đầy đủ các namespace.
  3. Cập nhật `routing.ts`, `LocaleContext.tsx`, `LanguageSwitcher.tsx`, `SidebarUserProfile.tsx`.
  4. Cập nhật `sprint-status.yaml` và `epics.md` để ghi nhận Story 7.8.
