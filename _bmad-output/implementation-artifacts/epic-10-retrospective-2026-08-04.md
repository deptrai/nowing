---
retro_key: epic-10-retrospective
epic: 10
epic_title: Connector & Scraper Expansion
date: 2026-08-04
status: completed
---

# Retrospective — Epic 10: Connector & Scraper Expansion

## 1. Epic Summary

Epic 10 expands the built-in scraper surface (FR-6) to cover Vietnamese real-estate (BĐS) sources and introduces a cross-source aggregator with trust/conflict scoring.

- **10.1** — `batdongsan.scrape`: mobile-API `p_sync` with gzip/base64/nibble-swap decoding, typed listings, phone unmasking via authenticated session, and per-account cookie rotation.
- **10.2** — `chotot_bds.scrape`: public JSON listing pages, headless/anti-bot fallback, typed listings with `seller_type`.
- **10.3** — `muaban_bds.scrape`: public BĐS listings, phone retrieval from `__NEXT_DATA__` / phone-show API, typed listings.
- **10.4** — `vn_bds.aggregate`: fan-out to child scrapers, normalize/dedupe, confidence scoring, price-conflict flags, provenance, and billing for both the aggregate query and child runs.

All four stories are marked `done` in the sprint status file (`_bmad-output/implementation-artifacts/sprint-status.yaml:115-118`). The epic touches `FR-6`, `FR-32` (deduplication/confidence), and `FR-39` (provenance), and is governed by `AD-3` (self-registering capability), `AD-11.1` (provenance recipe), `AD-16` (license boundary between BSL fetchers and Apache-2.0 capabilities), and `AD-19` (degrade instead of hard-fail under anti-bot pressure).

## 2. Delivery Metrics

| Metric | Value |
|--------|-------|
| Stories planned | 4 |
| Stories completed | 4 (100%) |
| Epic status in sprint-status | `in-progress` (pending this retro) |
| New backend modules | `app/proprietary/platforms/batdongsan/`, `chotot/`, `muaban_bds/`; `app/capabilities/{batdongsan,chotot,muaban_bds}/scrape/`; `app/capabilities/vn_bds/aggregate/`; `app/services/bds_aggregator/` |
| New agent subagents | `batdongsan`, `chotot_bds`, `muaban_bds` |
| New billing units | `BATDONGSAN_ITEM`, `CHOTOT_BDS_ITEM`, `MUABAN_BDS_ITEM`, `VN_BDS_AGGREGATE_QUERY` |

## 3. Quality & Technical Gate Summary

Gates were run on `develop` at commit `0eba86e9ed66527e2f0bfe661a19c7fc1c4e4ed2` (10.1/10.2/10.3 baseline) / `cca81a7f6d5060ada95766d2fec418375f09fd9a` (10.4 baseline).

| Gate | Scope | Result |
|------|-------|--------|
| **sprint-status** | 10.1–10.4 | `done` (`sprint-status.yaml:115-118`) |
| **Unit tests — batdongsan** | `tests/unit/platforms/batdongsan` + `tests/unit/capabilities/batdongsan` | 92 passed |
| **Unit tests — chotot + muaban_bds** | `tests/unit/platforms/{chotot,muaban_bds}` + `tests/unit/capabilities/{chotot,muaban_bds}` | 41 passed (chotot 25, muaban_bds 16) |
| **Unit tests — aggregator** | `tests/unit/services/bds_aggregator` | 28 passed |
| **Unit tests — vn_bds aggregate** | `tests/unit/capabilities/vn_bds/aggregate` | 5 passed |
| **Integration tests — scrapers** | `tests/integration/capabilities/{batdongsan,chotot}/scrape` | 4 passed, 2 skipped (live `SCRAPE_LIVE=1`) |
| **Integration tests — aggregator** | `tests/integration/capabilities/vn_bds/aggregate` | 3 passed |
| **Lint (ruff)** | `app/proprietary/platforms/{batdongsan,chotot,muaban_bds}`, `app/services/bds_aggregator`, `app/capabilities/{batdongsan,chotot,muaban_bds,vn_bds}` | clean |
| **Typecheck (frontend)** | `pnpm tsc --noEmit` (Nowing web) | clean |
| **Biome (frontend)** | `app/admin/scraper-accounts/page.tsx`, `lib/apis/scraper-platform-accounts-api.service.ts` | clean |
| **Docs drift** | `python3 scripts/check-docs-drift.py` | PASSED |

**Note on one flaky failure:** when the full Epic 10 test set was run in a single session, `tests/unit/services/bds_aggregator/test_orchestrator.py::test_min_confidence_filter` failed once after ~90 s and produced live network traffic to `muaban.net/api/v1/phone/show`. Re-running the test in isolation, and re-running the whole `bds_aggregator` suite, both pass cleanly. The flakiness appears tied to a unit test that can reach the network under shared test state.

## 4. What Went Well

1. **Reused the existing capability/scraper pattern and respected license boundaries.** All three scrapers follow the `reddit.scrape` pattern: proprietary fetch/parsing lives under `app/proprietary/platforms/<platform>/` (BSL 1.1), while the capability contract, executor, and REST/MCP exposure live under `app/capabilities/<platform>/scrape/` (Apache-2.0). This is explicitly called out in `10-1-batdongsan-scraper.md:152`, `10-2-chotot-bds-scraper.md:81-82`, `10-3-muaban-bds-scraper.md:81`, and `10-4-vn-bds-aggregator.md:127-130`.

2. **Degraded-mode and anti-bot handling was designed in from the start.** Each scraper returns `degraded=true` with a typed `degradation_reason` (`api_error`, `rate_limited`, `decode_error`, `bot_detected`, `layout_changed`, `empty`, `unknown`) rather than hard-failing. This matches `AD-19` and is especially important for batdongsan, where HTML detail pages sit behind Cloudflare and the mobile API is the primary path (`10-1-batdongsan-scraper.md:62-64`, `10-2-chotot-bds-scraper.md:61-64`, `10-4-vn-bds-aggregator.md:154`).

3. **Phone unmasking and admin credential UI were built as shared platform infrastructure.** `ScraperPlatformAccount`, the `/admin/scraper-accounts` page, and `scripts/capture_batdongsan_session.py` support batdongsan now and chotot/muaban if they later require auth. Batdongsan can execute the `DecryptPhone` XHR in a page context; muaban can call `POST /api/v1/phone/show` with `phone_enc`; both fall back to masked display instead of failing (`10-1-batdongsan-scraper.md:76-83`, `10-3-muaban-bds-scraper.md:93-104`).

4. **The cross-source aggregator delivered a clean, testable service layer.** `app/services/bds_aggregator/` separates normalize, dedupe, scoring, and orchestration, making unit testing straightforward. It supports fan-out to child scrapers, weighted confidence scoring, price-conflict flags, and provenance per `AD-11.1` (`10-4-vn-bds-aggregator.md:87-92`, traceability table at `10-4-vn-bds-aggregator.md:112-120`).

5. **All targeted quality gates passed.** Ruff, frontend typecheck, Biome, and docs-drift are clean; unit and integration tests for the new modules pass. The billing model for the aggregator correctly combines a per-query unit (`VN_BDS_AGGREGATE_QUERY`) with passthrough child costs, and only charges non-degraded child runs (`10-4-vn-bds-aggregator.md:148-151`).

## 5. What Could Be Better / Lessons Learned

1. **Story artifact headers and status are stale and inconsistent with sprint-status and code.**
   - `10-1-batdongsan-scraper.md:13` says `done` (correct).
   - `10-2-chotot-bds-scraper.md:13` says `ready-for-dev` even though every task and review patch is checked and tests pass.
   - `10-3-muaban-bds-scraper.md:13` says `ready-for-dev` and its task list at `10-3-muaban-bds-scraper.md:79-84` is unchecked, even though code and tests exist.
   - `10-4-vn-bds-aggregator.md:13` says `in-progress`, although the completion notes at `10-4-vn-bds-aggregator.md:195-198` claim the story is done.
   - *Lesson:* when a story reaches `done` in `sprint-status.yaml`, the corresponding story artifact front matter and task list must be updated in the same commit/transition to avoid confusion during retrospectives and code review hand-off.

2. **One aggregator unit test appears to hit the live network and is order-dependent/flaky.**
   `test_min_confidence_filter` failed once during a full-suite run with real `muaban.net` phone API calls, then passed on rerun and in isolation. The orchestrator test should inject fake child executors or use recorded fixtures and never make outbound calls in unit tests. This is a quality gap in `tests/unit/services/bds_aggregator/test_orchestrator.py`.

3. **Typecheck for the new Python modules was not run as a gate.** `10-4-vn-bds-aggregator.md:192` explicitly notes: *"Không có type checker (`mypy`/`pyright`) được cài trong môi trường hiện tại nên chưa chạy typecheck."* For a shared service like `bds_aggregator` that multiple scrapers will depend on, static type checking should be part of the standard gate.

4. **Aggregator scoring and conflict heuristics are hard-coded and not yet eval-gated.** The confidence formula (`0.25*source_trust + 0.35*overlap + 0.15*freshness + 0.25*price_consistency`), source-trust weights, and the 20% price-conflict threshold are constants in `scoring.py` without a baseline dataset or ratification flag. Before the feature is promoted to users, an output-quality eval should be added (similar to `nowing_evals` for memory recall in E3.9).

5. **The aggregator output is intentionally not written to `Memory` / `ResearchThread` in V1**, which is a reasonable scope cut but leaves a hand-off question for the next epic: when do aggregated listings become project memory, and how will they re-validate? This is noted as a non-goal in `10-4-vn-bds-aggregator.md:25-28` and should be revisited with the product owner.

## 6. Action Items for Next Epic

| # | Action | Owner | Acceptance Criteria |
|---|--------|-------|---------------------|
| 1 | Update stale story artifact headers/status for 10.2, 10.3, 10.4 and fix the `[backlog]` marker for 10.4 in `epics.md` | Agent / SM | `sprint-status.yaml`, `epics.md`, and all four `10-*.md` files show consistent `done` status |
| 2 | Harden `bds_aggregator` unit tests against live network and shared-state flakiness | Backend / Agent | `test_min_confidence_filter` and other orchestrator tests pass deterministically in a single full-suite run with no outbound `*.net` calls |
| 3 | Add an aggregator output-quality eval-gate with an oracle dataset for dedupe, confidence, and price-conflict detection | Data / QA | A new `nowing_evals` or `tests/evals/bds_aggregator` suite exists; `baseline_ratified` is tracked |
| 4 | Enforce static typechecking for `app/services/bds_aggregator` and `app/capabilities/vn_bds` as a CI gate | DevOps / Backend | `mypy` or `pyright` passes on the two packages; CI fails on new type errors |
| 5 | Capture Epic 10 verification commands in `AGENTS.md` for future maintainers | Agent | `AGENTS.md` contains the exact `pytest`, `ruff`, `tsc`, `biome`, and `check-docs-drift` commands used in this retro |

## 7. Stale Documentation Noted

- `epics.md` line `921` still lists Story 10.4 as `[backlog]`, and the Epic 10 summary at `epics.md:122` also shows 10.4 as `[backlog]` (and 10.1 as `[review]`), despite all stories being `done` in `sprint-status.yaml`. This retro recommends updating those markers to `[done 2026-08-04]` and `[done 2026-08-04 — per-account rate limit & cookie rotation added; AC-8 updated]` for 10.1 to match the detailed header at `epics.md:865`.

- The story artifacts `10-2-chotot-bds-scraper.md`, `10-3-muaban-bds-scraper.md`, and `10-4-vn-bds-aggregator.md` have stale `status` front matter and/or unchecked task lists. These should be reconciled as part of Action Item 1.

## 8. Significant Discoveries & Closing Notes

- **Reusable platform-account abstraction.** The combination of `ScraperPlatformAccount`, `scraper_platform_account_service.py`, and the `/admin/scraper-accounts` page gives the team a pattern for adding authenticated scrapers without re-building credential management per platform.
- **Degrade-don’t-fail is essential for real-estate scrapers.** All three Vietnamese sites (batdongsan, chotot, muaban) use anti-bot, JS rendering, or obfuscated APIs. The `degraded` output model keeps agent/chat flows from crashing when a source is blocked.
- **Cross-source confidence needs a baseline.** The aggregator is technically complete, but its business value (trust score, fake/duplicate detection) depends on an eval-gated, data-driven confidence model. Treat the current weights as a placeholder until an eval baseline is ratified.
- **Epic 10 is code-complete and ready to close.** All targeted stories pass their tests, quality gates, and review findings; the remaining work is documentation reconciliation, test hardening, and eval-gating the aggregator model.

---

**Artifacts referenced:**
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/planning-artifacts/epics.md` §Epic 10
- `_bmad-output/implementation-artifacts/10-1-batdongsan-scraper.md`
- `_bmad-output/implementation-artifacts/10-2-chotot-bds-scraper.md`
- `_bmad-output/implementation-artifacts/10-3-muaban-bds-scraper.md`
- `_bmad-output/implementation-artifacts/10-4-vn-bds-aggregator.md`
