# Story 27.1b Validation Report — 2026-08-25

**Story file:** `_bmad-output/implementation-artifacts/stories/27-1b-web-app-build-preview-runner.md`  
**Baseline:** `d06d121a0`  
**Status:** `in-progress`  
**Validator:** Devin  

---

## TL;DR

Story 27.1b **tồn tại nhưng đã lỗi thời và thiếu sót nghiêm trọng** so với code hiện tại. Nhiều phần được ghi là "GAP" thực ra đã được 27.1a hoặc baseline xây dựng. Story **thiếu rõ ràng về build/preview runner**, **thiếu bảo mật thực thi npm**, **thiếu chi phí `web_builder_build`**, và **thiếu integration với endpoint preview hiện có**. Không nên đưa cho dev agent implement ngay mà không cập nhật.

---

## 1. Những gì đã xây thực tế (mà story ghi nhầm là GAP)

| Story ghi | Thực tế code | Hệ quả |
|---|---|---|
| "No `app/services/web_builder/`" | Module đã tồn tại: `generator.py`, `project_writer.py`, `preview_renderer.py`, `deploy_service.py`, `mark_tool.py`, `schemas.py`, `validator.py` | Dev agent có thể tạo file trùng hoặc bỏ qua pattern hiện có |
| "No `app/routes/web_builder_routes.py`" | File đã tồn tại với `POST /apps` (generate), `GET /apps/{app_id}/preview`, `POST /apps/{app_id}/publish`, `/custom-domain`, `/mark`, `/files` | Story cần sửa thành "UPDATE route `/preview`" thay vì "NEW" |
| "No `WorkspaceApp` table" | `app/db.py:6559` `WorkspaceApp` đã có đầy đủ `workspace_id`, `slug`, `status`, `preview_url`, `public_url`, `container_id`, `port`, `custom_domain`, v.v. | Dev agent sẽ sai lệch về việc cần migration mới |
| "No `app/capabilities/web_builder/build_app/`" | `definition.py`, `executor.py`, `schemas.py` đã có và đăng ký `web_builder.build_app` | Story cần note "update executor" thay vì "create" |
| `WEB_BUILDER_ENABLED`, `WEB_BUILDER_STORAGE_PATH` chưa có | `app/config/__init__.py:1816-1827` đã có `WEB_BUILDER_ENABLED`, `WEB_BUILDER_MAX_PROMPT_CHARS`, `WEB_BUILDER_PUBLIC_APPS_PATH`, `WEB_BUILDER_DEPLOY_COST_MICROS` | Cần thêm `WEB_BUILDER_BUILD_COST_MICROS` và `BUILD_*` config, không phải từ đầu |
| `Workspace.web_builder_enabled` chưa có | `app/db.py:1948` đã có, default `true` | Dev agent không cần thêm |

---

## 2. Critical Issues (phải sửa trước khi dev)

### C1 — Build/preview mechanism quá mơ hồ
- AC-2 ghi: "`BuilderService` runs `npm install` followed by `next build` (or `next dev` for preview)".
- **Vấn đề:** `next dev` không phù hợp để làm preview ổn định (HMR, dev server, treo process). Nên xác định rõ:
  - `npm install` → `next build` với `output: 'standalone'` → `next start` từ `.next/standalone`.
  - Preview URL trỏ đến một tiến trình `next start` hoặc reverse-proxy internal port.
  - Hoặc dùng `next dev` cho quick preview nhưng có timeout, kill, và **không** dùng cho production.
- **Hệ quả nếu không sửa:** dev agent chọn `next dev` làm preview, gây treo tiến trình, leak tài nguyên.

### C2 — Không đề cập AD-113a (static-hosting exception) và preview hiện tại
- 27.1a đã ship với `PreviewRenderer.render_app_html()` (browser-compile TSX qua Babel/Tailwind CDN) và static publish.
- 27.1b sẽ thay thế/cải tiến preview, nhưng **không được phá vỡ** 27.1a static publish đang chạy.
- Story cần ghi rõ: route `GET /apps/{app_id}/preview` hiện dùng `PreviewRenderer`; 27.1b cần thêm `/apps/{app_id}/build` hoặc tích hợp build trước khi preview.

### C3 — Thiếu bảo mật khi chạy `npm install`
- `npm install` sẽ thực thi `preinstall`/`postinstall` scripts, tải binary từ mạng, viết file tuỳ ý.
- Story chỉ ghi "no `eval`/`exec`" — **không đủ**.
- Cần bắt buộc:
  - Chạy trong container/network sandbox hoặc dùng `npm ci --ignore-scripts`.
  - Network egress restricted hoặc offline package cache.
  - `node_modules` được mount trong thư mục riêng, không ảnh hưởng host.

### C4 — Thiếu rõ ràng về chi phí `web_builder_build`
- AC-3 đòi `TokenUsage` `usage_type="web_builder_build"`.
- Story không nói `cost_micros` tính từ đâu: flat fee, LLM cost, compute time?
- Cần định nghĩa `WEB_BUILDER_BUILD_COST_MICROS` hoặc cách tính dựa trên thời gian build / CPU.

### C5 — Thiếu giới hạn tài nguyên và concurrency
- Không có timeout, max concurrent builds, disk quota, cleanup failed builds.
- Cần: `WEB_BUILDER_BUILD_TIMEOUT_SECONDS`, `WEB_BUILDER_MAX_CONCURRENT_BUILDS`, builder queue hoặc Celery task, xoá `.next` cũ.

### C6 — Thiếu integration với `web_builder_routes.py`
- Hiện `GET /apps/{app_id}/preview` trả `PreviewRenderer`.
- Story cần chỉ rõ: thêm bước build, cập nhật `WorkspaceApp.status` (`generated` → `building` → `build_failed`/`preview_ready`), và trả preview từ build output.

### C7 — Thiếu chi tiết về Node/npm runtime
- Không nêu Node version, package manager (npm vs pnpm), cách ensure runtime trong container.
- Cần ghi: project sinh ra dùng npm; build runner chạy trong môi trường có Node 20+; nếu thiếu runtime thì trả `build_failed`.

---

## 3. Enhancement Opportunities (nên bổ sung)

| # | Đề xuất | Lý do |
|---|---|---|
| E1 | Thêm section "Current State" liệt kê file/code đã có dựa trên audit 2026-08-25 | Tránh dev agent nhìn nhầm GAP |
| E2 | Thêm `BuilderService` contract với state machine `generated → building → preview_ready / build_failed` | Rõ ràng hành vi và DB update |
| E3 | Thêm `web_builder_build` TokenUsage với config `WEB_BUILDER_BUILD_COST_MICROS` | Hoàn thành AC-3 |
| E4 | Thêm chi tiết `next.config.js` phải có `output: 'standalone'` | Để chạy `next start` từ `.next/standalone` |
| E5 | Thêm AC cho build logs API/UI | Lỗi build cần debug được |
| E6 | Thêm hermetic test strategy: mock `npm`/`next` hoặc fixture có `package.json` sẵn | `npm install` trong test chậm và flaky |
| E7 | Thêm `builder.py` expected public API và cách `WebBuilderService` gọi nó | Giảm ambiguity |
| E8 | Thêm relationship với 27.1c: output của builder (`.next/standalone`) là input cho container deploy | Tránh duplicate logic |
| E9 | Thêm `preview_url` semantics: path-based (`/apps/{id}/preview`) hay port-based internal | Ảnh hưởng routing |

---

## 4. LLM Optimization Suggestions

- **Bỏ [BUILT] list mơ hồ**; thay bằng bảng "Existing Assets" với file path và line.
- **Chuyển [GAP] thành "Implementation Steps"** có thứ tự.
- **Rút gọn ACs**, nhấn mạnh điều kiện đầu ra.
- **Thêm "What NOT to do"** (không dùng `next dev` cho production preview, không chạy npm scripts tuỳ tiện).

---

## 5. Verdict

Story 27.1b **chưa đủ để giao cho dev agent**. Cần cập nhật:

1. Sửa [BUILT]/[GAP] cho đúng với code hiện tại.
2. Bổ sung AD-113a, AD-120, AD-121 context.
3. Làm rõ build mechanism (`next build` + standalone output).
4. Thêm bảo mật, concurrency, cost model.
5. Cập nhật integration với `web_builder_routes.py` `GET /preview`.
6. Thêm test strategy.

Nếu không sửa, dev agent có nguy cơ:
- Tạo file trùng.
- Dùng `next dev` làm preview gây leak process.
- Bỏ qua `TokenUsage` `web_builder_build`.
- Bỏ qua bảo mật `npm install`.

---

## 6. Recommended Next Action

Cập nhật story file `27-1b-web-app-build-preview-runner.md` trước khi chạy `dev-story`.
