---
title: 'Legal Brief — Upstream Attribution & License Structure (Nowing / SurfSense)'
type: legal-brief
status: ready-to-send
created: '2026-07-26'
owner: 'Founder + Legal'
tracks: 'AI-2026-07-25-7 (P0, blocks: public-repo)'
related:
  - _bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md  # AD-16, AD-16.1
  - _bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md  # §1.1 license table
  - _bmad-output/implementation-artifacts/sprint-status.yaml  # AI-2026-07-25-7
---

> ## ⚠️ HƯỚNG DẪN NỘI BỘ — XOÁ KHỐI NÀY TRƯỚC KHI GỬI
>
> **Gửi cho ai:** luật sư sở hữu trí tuệ / open-source licensing. Không cần biết code.
>
> **Gửi phần nào:** mọi thứ **từ dòng `SEND FROM HERE` trở xuống**. Khối này là ghi chú nội bộ.
>
> **Mọi số liệu trong brief đã được verify lại bằng git ngày 2026-07-26** (không lấy lại từ artifact cũ). Mỗi con số có lệnh tái lập kèm theo ở §3 để luật sư hoặc bên thứ ba tự kiểm.
>
> **🔴 Brief này SỬA một sai sót phạm vi của `AD-16.1`.** `AD-16.1` chỉ đo thư mục BSL (`app/proprietary/`) và kết luận "99,84% code kế thừa". Đo lại rộng hơn cho thấy: **toàn bộ repository là fork**, cả 7 component đều là rename 1:1, và **phần Apache-2.0 — tức toàn bộ sản phẩm còn lại — cũng kế thừa, 81% file byte-identical**. Nghĩa vụ attribution của Apache-2.0 §4 áp lên phần đó, không chỉ lên thư mục BSL. `AD-16.1` cần được amend sau khi có kết luận.
>
> **Việc cần làm sau khi có trả lời:** amend `AD-16.1` phạm vi · cập nhật PRD §1.1 (bảng license ba tầng) · quyết lại `D5` nếu cấu trúc BSL phải đổi · gỡ chặn `public-repo`.
>
> **Đừng đợi brief này để code.** `8-7` → `3-14` → `3-9` chạy song song, không phụ thuộc kết luận pháp lý.

---

# SEND FROM HERE

# Legal Brief — Upstream Attribution & License Structure

**Prepared:** 26 July 2026
**Subject:** Nowing (private repository, planned public release) and its upstream, SurfSense
**Prepared for:** external counsel, IP / open-source licensing
**Prepared by:** Nowing engineering

This document states facts and asks questions. It contains no legal conclusions, and we are not asserting that any obligation has or has not been met — that determination is what we are asking you for.

---

## 1. Why we are asking, and what depends on the answer

Nowing is a research-memory platform. It is currently a **private** repository. We intend to release it publicly under a dual-license structure, and we have built a commercial strategy on top of that structure.

While preparing for the public release, we established that **Nowing is a fork of an existing open-source project, SurfSense**, and that the attribution and licensing consequences of that fact were never addressed. Both license files in our repository are renamed copies of the upstream project's license files, including the copyright line and the Business Source License "Licensor" designation.

Two decisions are blocked on your answer:

1. **Whether we may publish the repository at all in its current state**, and what must change first.
2. **Whether a commercial positioning we have already committed to internally remains available.** Our current strategy treats the Business Source License restriction on one component as a competitive moat and a stated selling point. That component is, as measured below, almost entirely inherited code, and we have designated ourselves as its BSL Licensor. If that designation is not available to us, the strategy needs rework.

We have frozen the public release pending your input.

---

## 2. Summary of facts

All figures independently re-verified on 26 July 2026. Reproduction commands in §3.

### 2.1 The fork relationship

| Fact | Value |
|---|---|
| Upstream repository | `github.com/MODSetter/SurfSense` |
| Fork point (git merge-base) | commit `bea603e2253989970389eb26db56406c4070500c` |
| Upstream tag at fork point | `0.0.34.1` |
| Upstream commits reachable from fork point | **7,713** |
| Our own commits since fork point | **45** |
| Fork disclosed anywhere in our repository | **No** |

### 2.2 Scope — the whole product is inherited, not one directory

All seven product components are 1:1 directory renames of upstream components:

| Upstream | Nowing |
|---|---|
| `surfsense_backend` | `nowing_backend` |
| `surfsense_web` | `nowing_web` |
| `surfsense_desktop` | `nowing_desktop` |
| `surfsense_browser_extension` | `nowing_browser_extension` |
| `surfsense_obsidian` | `nowing_obsidian` |
| `surfsense_mcp` | `nowing_mcp` |
| `surfsense_evals` | `nowing_evals` |

Every top-level file is also inherited, including `LICENSE`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `README.md` and its four translations, `VERSION`, `manifest.json`, `versions.json`, and the `docker/`, `docs/`, `scripts/`, `.github/` directories.

The only directories that are ours and not upstream's are AI-tooling configuration (`.agents`, `.claude`, `.devin`, `.kiro`, `_bmad`) — not product code.

### 2.3 Divergence, measured on source files

**Apache-2.0 portion** (backend application Python, excluding the BSL directory):

| Measure | Count |
|---|---|
| Upstream files at fork point | 1,227 |
| **Byte-identical in Nowing** | **993 (81%)** |
| Modified | 234 |
| Deleted or moved | 0 |

**BSL portion** (`nowing_backend/app/proprietary/` — a web-crawler engine: per-platform fetchers, anti-bot/stealth tuning, CAPTCHA handling, session pooling, test harness):

| Measure | Count |
|---|---|
| Python files, each side | 84 / 84 |
| Relative paths matching | 84 / 84 (100%) |
| **Byte-identical** | **73 / 84 (87%)** |
| Files with any difference | 11 |
| Total changed lines across those 11 files | **26** (of ~16,586 lines — 0.16%) |
| **Nature of all 26 changed lines** | String substitution `SurfSense` → `Nowing` in comments and docstrings, plus one attribute value `name = "surfsense_site"` → `"nowing_site"`. **No functional change.** |

The 26 changed lines, in full, are reproduced in §5.2.

### 2.4 License files — renamed copies

**Root `LICENSE`** (dual-license declaration + full Apache-2.0 text):

| Field | Upstream | Nowing |
|---|---|---|
| Copyright line | `Copyright (c) SurfSense` | `Copyright (c) Nowing` |
| BSL directory referenced | `surfsense_backend/app/proprietary/` | `nowing_backend/app/proprietary/` |
| Third-party components sentence | "...into the SurfSense software..." | "...into the Nowing software..." |
| Everything else | — | **identical** |

**`app/proprietary/LICENSE`** (Business Source License 1.1):

| BSL Parameter | Upstream | Nowing |
|---|---|---|
| `Licensor` | `SurfSense` | **`Nowing`** |
| `Licensed Work` | "The SurfSense Proprietary Components... (c) 2026 SurfSense" | "The Nowing Proprietary Components... (c) 2026 Nowing" |
| `Additional Use Grant` | — | **identical** |
| `Change Date` | Four years from public release | **identical** |
| `Change License` | Apache License 2.0 | **identical** |
| MariaDB license text and Covenants | — | **identical** |

In both cases the upstream copyright and Licensor designations were **replaced**, not supplemented.

### 2.5 What is absent

- **No `NOTICE` file** in our repository. (Upstream has none either.)
- **No attribution to SurfSense** in `README.md`, `LICENSE`, or anywhere else in the repository.
- The only remaining references to the upstream author are two apparent **leftovers from the rename**, which are not attribution and are arguably misleading, because they point at the upstream author's own assets while labelled with our product name:
  - `README.md:20` — a third-party badge whose alt text reads `MODSetter%2FNowing`
  - `README.md:255` — a link labelled "Nowing Project Board" pointing to `github.com/users/MODSetter/projects/3`

---

## 3. How to reproduce every figure above

Requires a clone of our repository with the upstream remote configured. No special tooling.

```bash
# 2.1 — fork relationship
git remote -v                                  # upstream = github.com/MODSetter/SurfSense.git
git merge-base HEAD upstream/main               # -> bea603e2253989970389eb26db56406c4070500c
git describe --tags upstream/main               # -> 0.0.34.1
git rev-list --count bea603e22                  # -> 7713   (upstream commits at fork point)
git rev-list --count bea603e22..HEAD            # -> 45     (our commits since)

# 2.2 — component-level scope
git ls-tree --name-only bea603e22               # upstream top level
git ls-tree --name-only HEAD                    # ours

# 2.3 — license file comparison
git show upstream/main:LICENSE
git show upstream/main:surfsense_backend/app/proprietary/LICENSE
diff <(git show upstream/main:surfsense_backend/app/proprietary/LICENSE) \
     nowing_backend/app/proprietary/LICENSE

# 2.3 — BSL directory: identical-file count and the 26 changed lines
for f in $(git ls-tree -r --name-only upstream/main \
           -- surfsense_backend/app/proprietary | grep '\.py$'); do
  rel=${f#surfsense_backend/app/proprietary/}
  git show "upstream/main:$f" | diff - "nowing_backend/app/proprietary/$rel"
done
```

We can provide a signed archive of both trees at the fork point on request.

---

## 4. Current license structure as declared

Our repository declares three tiers. Tier 3 does not live in the repository.

| Tier | Scope | Declared license | Status |
|---|---|---|---|
| **1. Core** | Everything outside `nowing_backend/app/proprietary/` — memory layer, knowledge base, chat, automations, deliverables, five client applications, billing | Apache License 2.0 | 81% byte-identical to upstream (§2.3) |
| **2. Crawler engine** | `nowing_backend/app/proprietary/**` — 84 files, ~16,586 lines | Business Source License 1.1, **Licensor: Nowing** | 87% byte-identical to upstream; 0.16% of lines changed, all cosmetic (§2.3) |
| **3. Deep-research engine** | Not in this repository | Closed source, operated as a hosted service | Written by us. Not inherited. Not at issue here. |

---

## 5. What was changed, and what was not

### 5.1 Changed
- Product name throughout (directory names, package names, user-facing strings, documentation).
- The copyright holder line in the root `LICENSE`, and the `Licensor` / `Licensed Work` parameters in the BSL file (§2.4).
- 234 of 1,227 Apache-2.0 backend Python files carry substantive modifications by us — new features (a long-term memory subsystem, an integration with our hosted research engine, billing changes) built on the inherited base.

### 5.2 Not changed — the complete set of differences inside the BSL directory

All 26 differing lines across all 11 differing files, verbatim:

```
__init__.py                              "SurfSense proprietary packages"  -> "Nowing proprietary packages"
web_crawler/captcha.py                   "# SurfSense proprietary crawler engine." -> "# Nowing ..."
web_crawler/connector.py                 "# SurfSense proprietary crawler engine." -> "# Nowing ..."
web_crawler/site_crawler.py              "# SurfSense proprietary crawler engine." -> "# Nowing ..."
web_crawler/site_crawler.py              name = "surfsense_site"           -> name = "nowing_site"
web_crawler/stealth.py                   "# SurfSense proprietary crawler engine." -> "# Nowing ..."
web_crawler/testbench/__init__.py        "# SurfSense proprietary crawler engine." -> "# Nowing ..."
web_crawler/testbench/__main__.py        "# SurfSense proprietary crawler engine." -> "# Nowing ..."
web_crawler/testbench/core.py            "# SurfSense proprietary crawler engine." -> "# Nowing ..."
web_crawler/testbench/suite_extraction.py "# SurfSense proprietary crawler engine." -> "# Nowing ..."
web_crawler/testbench/suite_stealth.py   "# SurfSense proprietary crawler engine." -> "# Nowing ..."
web_crawler/url_policy.py                "# SurfSense proprietary crawler engine." -> "# Nowing ..."
web_crawler/url_policy.py                "these two primitives remain SurfSense-owned." -> "... Nowing-owned."
```

Note the final line: a source comment asserting ownership was rewritten from the upstream author's name to ours.

---

## 6. Commercial context relevant to the questions

We include this because it may change your analysis.

**We operate a separate hosted service.** Tier 3 above — a deep-research engine — is closed source, is not in this repository, and is offered to customers as a paid hosted service. Our product calls it over HTTP. Parts of the inherited Tier 2 crawler code may contribute value to that offering.

The BSL 1.1 Additional Use Grant (identical text on both sides) permits production use but excludes offering *"the Licensed Work, or any product or service whose value derives, entirely or substantially, from the Licensed Work, to third parties as a commercial product or as a hosted or managed service."*

**We currently market the BSL restriction as our own protective moat**, in internal strategy documents and in draft public copy. Independently of the legal question, we have already suspended that claim internally as factually unsupportable, given that the protected component is 87% byte-identical to inherited code.

**We are not currently redistributing.** The repository is private and has never been published. Whether obligations have already been triggered by internal or production use, as opposed to distribution, is one of our questions.

---

## 7. Questions for counsel

### Q1 — Apache-2.0 attribution: is replacement sufficient, or must the upstream notice be retained?
Apache-2.0 §4 imposes conditions on redistribution, including retention of copyright notices and a `NOTICE` file where one exists.

- We **replaced** the upstream copyright line rather than adding ours alongside it. Does §4 permit that?
- Upstream ships no `NOTICE` file. Does that reduce, or leave unchanged, our obligation to attribute?
- §4(b) requires modified files to carry prominent notice of change. 234 files are modified and none carries such a notice. What form is required?
- Does the obligation attach to the whole inherited Apache-2.0 tree (§2.3: 993 unmodified files), or only to files we touched?

### Q2 — May we designate ourselves as BSL Licensor for inherited code?
The BSL 1.1 parameters were copied and the `Licensor` field changed from the upstream project to ours.

- Can a downstream party validly name itself Licensor of a Licensed Work it did not author?
- What effect does the upstream project's own BSL grant have on our derivative? Upstream's BSL grants rights to *copy, modify, create derivative works, redistribute, and make non-production use*, plus production use under the Additional Use Grant. Does that grant extend to re-licensing under our own name?
- MariaDB's "Covenants of Licensor" §4 states the licensor undertakes *not to modify this License in any other way*. Is changing the Licensor and Licensed Work parameters within the permitted parameterisation, or does it exceed it?
- If we cannot be Licensor, what are our options? Retain upstream as Licensor? Relicense that directory? Remove it?

### Q3 — Does our hosted service implicate the Additional Use Grant?
Given §6: we operate a paid hosted service, separate from this repository, that may derive value from the inherited BSL component.

- Does the upstream Additional Use Grant restrict that, and if so how far does *"value derives, entirely or substantially"* reach?
- Does it matter that the hosted service is a distinct codebase invoking the component over a network boundary, rather than bundling it?
- Our engineering plan deliberately routes so that the hosted engine never invokes the BSL code directly (the component runs only inside our own product, and the hosted engine merely signals when it cannot retrieve a page). Does that architectural separation matter legally, or is it immaterial?

### Q4 — What must be in place before we publish?
Concretely, and in the order you would sequence it:

- `NOTICE` file — required? What content?
- `README` / `LICENSE` attribution — required? What wording?
- Per-file headers across the inherited tree — required, or is repository-level attribution sufficient?
- Anything to be removed rather than attributed?
- Should we notify or seek consent from the upstream author before publishing?

### Q5 — Exposure from the period before publication
The repository has never been published, but the software has been run and developed against internally.

- Have any obligations already been triggered by use without distribution?
- Does our current draft public copy — which describes the product as open source and the BSL component as our own engineering — create separate exposure (misrepresentation, or trademark/attribution issues) independent of the license terms?

---

## 8. Options we are weighing

Listed so you can react to them rather than construct them. We have no preference yet and will follow your advice.

| # | Option | Our open question |
|---|---|---|
| **A** | Full attribution, structure unchanged: add `NOTICE`, credit upstream in `README`/`LICENSE`, add §4(b) change notices, restore upstream copyright alongside ours, keep the BSL tier | Is this sufficient, and does it resolve Q2? |
| **B** | Attribution as in A, **plus** restore upstream as BSL Licensor for `app/proprietary/` | Does this leave us able to operate commercially at all? |
| **C** | Remove the inherited BSL component and rebuild or replace it | Highest engineering cost; does it fully clear the issue, including for versions already run internally? |
| **D** | Seek an explicit licence or written consent from the upstream author | Practical? What would we need to offer or disclose? |
| **E** | Keep the repository private indefinitely | Abandons the strategy but avoids distribution obligations. Does it avoid Q5? |

---

## 9. What we can provide

- Read access to the private repository.
- A signed archive of both source trees at the fork point.
- A complete file-level divergence report (any granularity).
- Our internal strategy documents describing the intended commercial use, including the draft public copy referenced in §6.
- Engineering time to answer technical questions.

**Contact:** *(fill in before sending)*
