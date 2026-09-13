---
title: 'Giải quyết deferred QA findings Story 26-7 Hermetic Quality Gates'
type: 'chore'
created: '2026-09-10'
status: 'completed'
baseline_commit: '755f99aa64a24618fef50e85e2dbd209dbfe666a'
completed_commit: null
review_loop_iteration: 0
context:
  - _bmad-output/implementation-artifacts/deferred-work.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 26-7 để lại 3 deferred QA findings: `phone_extractor.py` compile regex mỗi lần gọi; `is_valid_vietnam_tax_code` chưa validate trên 100 MST thật; thiếu hermetic FastMCP integration test cho `dsh_worker` / `nowing_mcp`.

**Approach:** Pre-compile regex ở module level, thêm fixture corpus MST, và viết hermetic integration test dùng `tests/e2e/fakes/mcp_runtime.py` để giải quyết 3 findings mà không đổi behavior sản phẩm.

## Boundaries & Constraints

**Always:**
- Chỉ sửa code QA/test/performance nhỏ; không đổi logic business extraction, validation, hay xactions adapter.
- Pre-compile regex theo convention `_REGEX` viết hoa ở module level.
- Fixtures MST tách thành file JSON riêng để tái sử dụng.
- Hermetic test dùng `mcp_runtime` fake, không gọi network thật.

**Ask First:**
- Nếu masothue fixtures không đủ 100 mã số thật public, giảm xuống 50 và document lý do.
- Nếu `dsh_worker` không gọi `nowing_mcp` trực tiếp, xác nhận test qua `adapter_v2.py` hay `xactions_mcp_client.py`.

**Never:**
- Không đổi thuật toán Modulo-11.
- Không thêm dependency mới.
- Không viết integration test cần server MCP thật.

</frozen-after-approval>

## Code Map

- `nowing_backend/app/proprietary/platforms/xactions/phone_extractor.py` -- `normalize_vietnamese_text` compile `token_pattern` trong hàm; chuyển thành `_TOKEN_PATTERN` module level.
- `nowing_backend/app/proprietary/platforms/xactions/tax_code.py` -- `is_valid_vietnam_tax_code` dùng Modulo-11; cần test với fixture corpus.
- `nowing_backend/tests/unit/proprietary/platforms/xactions/test_phone_extractor.py` -- unit tests hiện có; chạy lại sau khi pre-compile.
- `nowing_backend/tests/unit/proprietary/platforms/xactions/test_tax_code.py` -- thêm test fixture-driven.
- `nowing_backend/tests/fixtures/masothue_tax_codes.json` -- file fixtures MST mới.
- `nowing_backend/tests/e2e/fakes/mcp_runtime.py` -- fake streamable-HTTP MCP runtime.
- `nowing_backend/app/proprietary/platforms/xactions/mcp_client.py` -- `XActionsMcpClient` dùng `streamablehttp_client`; target hermetic test.
- `nowing_backend/tests/integration/platforms/test_xactions_mcp_client_hermetic.py` -- hermetic integration test mới.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/proprietary/platforms/xactions/phone_extractor.py` -- pre-compile `_TOKEN_PATTERN` và các regex lặp trong `normalize_vietnamese_text`; chạy lại `test_phone_extractor.py`.
- [x] `nowing_backend/tests/fixtures/masothue_tax_codes.json` -- tạo file với 50–100 MST known-good, đảm bảo không phone-like.
- [x] `nowing_backend/tests/unit/proprietary/platforms/xactions/test_tax_code.py` -- thêm `test_is_valid_vietnam_tax_code_against_known_good_masothue_fixtures` load fixture và assert all pass.
- [x] `nowing_backend/tests/integration/platforms/test_xactions_mcp_client_hermetic.py` -- viết hermetic test dùng `mcp_runtime.register` + `mcp_runtime.install`; test `XActionsMcpClient.call_tool` và `list_tools` với fake transport.
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- cập nhật mục 26-7 thành `Resolved` với reference.

**Acceptance Criteria:**
- Given `phone_extractor.py` được sửa, when chạy `pytest tests/unit/proprietary/platforms/xactions/test_phone_extractor.py`, then tất cả tests pass.
- Given fixtures file tồn tại, when chạy `test_tax_code.py`, then `is_valid_vietnam_tax_code` trả về `True` cho 100% fixtures.
- Given `mcp_runtime` fake được cài đặt, when hermetic integration test chạy, then `XActionsMcpClient` hoàn thành `call_tool` và `list_tools` mà không cần network thật.
- Given 3 findings được giải quyết, when `deferred-work.md` được cập nhật, then các mục 26-7 chuyển thành `Resolved`.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/proprietary/platforms/xactions/test_phone_extractor.py tests/unit/proprietary/platforms/xactions/test_tax_code.py` -- expected: all GREEN.
- `cd nowing_backend && uv run pytest tests/integration/platforms/test_xactions_mcp_client_hermetic.py -m integration` -- expected: all GREEN.

**Manual checks:**
- `deferred-work.md` được cập nhật với `Resolved from: code review of 26-7...` cho 3 findings.
- `phone_extractor.py` không còn `re.compile` bên trong `normalize_vietnamese_text`.
