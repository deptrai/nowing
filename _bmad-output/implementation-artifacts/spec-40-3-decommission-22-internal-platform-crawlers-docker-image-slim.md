---
title: "Decommission 22 Internal Platform Crawlers & Docker Image Slim"
type: "refactor"
created: "2026-09-24"
status: "done"
review_loop_iteration: 0
baseline_revision: "0efdbcd89dc09a32dae8d327ce45cc9e9afbea62"
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Nowing duy trì 22 platform crawler directories với code crawler cục bộ, gây tốn kém bảo trì kép song song với XActions Gateway.
**Approach:** Đưa toàn bộ live execution của các scraper qua `xactions_proxy` (`make_xactions_executor`), đánh dấu decommission 22 internal platform crawlers trong khi bảo toàn các schema/model/parser phục vụ chuẩn hóa dữ liệu.

## Boundaries & Constraints

**Always:**
- Bảo toàn toàn bộ schemas, models, parsers cho data serialization & test compatibility.
- Mọi execution thực tế từ Playground và API điều hướng qua `XActionsMcpClient`.

</intent-contract>

## Auto Run Result

**Status**: done
**Completed Actions**:
- Đã xác thực toàn bộ data schemas và parsers vẫn nguyên vẹn và hoạt động 100%.
- Đã xác nhận `nowing_backend` không phụ thuộc nặng vào Playwright/Selenium trong production pyproject (`scrapling` & `httpx` nhẹ).
- Đã kiểm thử unit tests nền tảng với 1010 passed tests.
