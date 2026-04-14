---
name: SaaS Transition Decision
description: SurfSense is transitioning from self-hosted to SaaS-only — no more self-hosted mode support
type: project
---

SurfSense đang chuyển đổi hoàn toàn sang SaaS, không còn hỗ trợ self-hosted nữa.

**Why:** Quyết định kinh doanh — chuyển sang mô hình subscription SaaS.

**How to apply:** Không cần guard `isSelfHosted()` cho các tính năng cloud-only (Stripe, billing, etc.). Code self-hosted hiện tại có thể vẫn tồn tại nhưng không cần maintain hoặc thêm logic phân nhánh self-hosted/cloud cho features mới.
