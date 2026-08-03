# Legal Package — Upstream Code Attribution (Nowing / SurfSense)

**Prepared:** 2026-08-04  
**Package path:** `_bmad-output/planning-artifacts/legal-package-prep-2026-08-04.md`  
**NOTICE path:** `NOTICE`  
**Status:** DRAFT — prepared for external counsel; do **not** publish the repository before counsel clears this package.

---

## 1. Facts

### 1.1 Fork relationship

| Fact | Value | Source / command |
|---|---|---|
| Upstream repository | `github.com/MODSetter/SurfSense` | `git remote -v` → `upstream https://github.com/MODSetter/SurfSense.git` |
| Nowing origin | `github.com/deptrai/nowing.git` | `git remote -v` → `origin https://github.com/deptrai/nowing.git` |
| Fork point (merge-base) | `bea603e2253989970389eb26db56406c4070500c` | `git merge-base HEAD upstream/main` |
| Upstream tag at fork point | `0.0.34.1` | `git describe --tags bea603e2...` |
| Upstream commits at fork point | 7,713 | `git rev-list --count bea603e2...` |
| Our commits since fork point (current) | 120 | `git rev-list --count bea603e2...HEAD` |
| Upstream current tag | `0.0.35.4` | `git describe --tags upstream/main` |

The 120 post-fork commits is a material update: the 2026-07-26 legal brief reported 45 commits. Since then, the Apache-2.0 portion has shifted from 81% byte-identical to ~77.8%, and the BSL portion has acquired one functional (non-cosmetic) change.

### 1.2 Component mapping — all 7 product components are 1:1 directory renames

| Upstream (SurfSense) | Nowing |
|---|---|
| `surfsense_backend` | `nowing_backend` |
| `surfsense_web` | `nowing_web` |
| `surfsense_desktop` | `nowing_desktop` |
| `surfsense_browser_extension` | `nowing_browser_extension` |
| `surfsense_obsidian` | `nowing_obsidian` |
| `surfsense_mcp` | `nowing_mcp` |
| `surfsense_evals` | `nowing_evals` |

Every top-level file (`LICENSE`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `README.md` + its 4 translations, `VERSION`, `manifest.json`, `versions.json`, `docker/`, `docs/`, `scripts/`, `.github/`) is inherited (`legal-brief-upstream-attribution-2026-07-26.md` §2.2). The only Nowing-only directories are agent-tooling configuration (`.agents`, `.claude`, `.devin`, `.kiro`, `_bmad`), which are not product code.

### 1.3 Apache-2.0 core — current divergence

Measured against the fork point, for `*.py` under `surfsense_backend/app` excluding `app/proprietary`:

- Total upstream `.py` files at fork point: **1,227**
- Byte-identical in Nowing: **955** (**77.8%**)
- Changed: **272**
- Missing: **0**
- Approximate changed lines (unified diff `+`/`-` count, excluding `---`/`+++` headers): **6,383**

The current `nowing_backend/app` tree (excluding `proprietary`) contains **1,338** `.py` files, i.e. **111** `.py` files have been added beyond the 1,227 inherited at the fork point.

These figures are different from the 2026-07-26 brief (81% / 234 changed) because the repository has continued to evolve.

### 1.4 BSL crawler engine (`nowing_backend/app/proprietary/**`) — current divergence

Measured against the fork point, for `*.py` under `surfsense_backend/app/proprietary`:

- Total upstream `.py` files at fork point: **84**
- Byte-identical in Nowing: **72** (**85.7%**)
- Changed: **12**
- Missing: **0**
- Approximate changed lines (unified diff `+`/`-`): **42**
- New `.py` files in the directory not traceable to the fork point: **16** (the directory now has 100 `.py` files total)

Changed files at the fork point (with changed-line counts):

| Changed file | Changed lines | Nature |
|---|---|---|
| `__init__.py` | 2 | String substitution `SurfSense` → `Nowing` |
| `platforms/youtube/url_resolver.py` | 16 | **Functional change**: host-spoofing guard (added `_YOUTUBE_HOSTS`, hostname check) |
| `web_crawler/captcha.py` | 2 | String substitution `SurfSense` → `Nowing` |
| `web_crawler/connector.py` | 2 | String substitution |
| `web_crawler/site_crawler.py` | 4 | String substitution + `surfsense_site` → `nowing_site` |
| `web_crawler/stealth.py` | 2 | String substitution |
| `web_crawler/testbench/__init__.py` | 2 | String substitution |
| `web_crawler/testbench/__main__.py` | 2 | String substitution |
| `web_crawler/testbench/core.py` | 2 | String substitution |
| `web_crawler/testbench/suite_extraction.py` | 2 | String substitution |
| `web_crawler/testbench/suite_stealth.py` | 2 | String substitution |
| `web_crawler/url_policy.py` | 4 | String substitution |

All other changes in this directory are the `SurfSense` → `Nowing` renames noted in the 2026-07-26 brief. The `url_resolver.py` change is a post-2026-07-26 functional modification and is **not** cosmetic.

The 16 new files (not present at the fork point) are separate from the 84 inherited files and should be evaluated for their own authorship.

### 1.5 License files — renamed copies

#### Root `LICENSE` (`/Users/luisphan/Documents/GitHub/nowing/LICENSE`)

| Field | Upstream at fork point | Nowing (current) |
|---|---|---|
| Copyright line | `Copyright (c) SurfSense` | `Copyright (c) Nowing` (L1) |
| BSL directory referenced | `surfsense_backend/app/proprietary/` | `nowing_backend/app/proprietary/` (L5) |
| Third-party components sentence | `...into the SurfSense software...` | `...into the Nowing software...` (L8) |
| Everything else | — | identical |

#### `nowing_backend/app/proprietary/LICENSE` (`.../proprietary/LICENSE`)

| BSL Parameter | Upstream at fork point | Nowing (current) |
|---|---|---|
| `Licensor` | `SurfSense` | `Nowing` (L10) |
| `Licensed Work` | `The SurfSense Proprietary Components... (c) 2026 SurfSense` | `The Nowing Proprietary Components... (c) 2026 Nowing` (L12–15) |
| `Additional Use Grant` | identical | identical (L17–22) |
| `Change Date` | Four years from public release | identical (L24–25) |
| `Change License` | Apache-2.0 | identical (L27) |
| MariaDB license text + Covenants | identical | identical (L34–109) |

In both license files, the upstream copyright holder and BSL Licensor were **replaced**, not supplemented.

### 1.6 What is absent

- No `NOTICE` file existed before this package (`NOTICE` was created as part of this task).
- No attribution to `SurfSense` or `MODSetter` in `README.md`, `LICENSE`, or anywhere else.
- `README.md` still points at upstream author assets:
  - L20: Trendshift badge `alt="MODSetter%2FNowing | Trendshift"` linking to `trendshift.io/repositories/13606`.
  - L247: `Nowing Project Board` linking to `github.com/users/MODSetter/projects/3`.

### 1.7 `README.md` messaging violations around “open source”

The product brief and the GTM review both instruct not to call the **whole product** “open source” because the crawler engine is BSL 1.1, and BSL explicitly states it is not an open-source license.

Problematic lines in `README.md`:

| Line | Current text | Issue |
|---|---|---|
| L1 | `alt="Nowing — open-source AI research workspace..."` | Product-level “open source” claim. |
| L20 | `alt="MODSetter%2FNowing \| Trendshift"` + link `trendshift.io/repositories/13606` | Uses upstream author/repo branding; points at upstream asset. |
| L23 | `# Nowing: Open-Source Research Memory for AI Agents` | Product-level “open source” in the H1. |
| L25 | `> **Nowing is open-source research memory for AI agents...**` | Product-level tagline. |
| L27 | `powered by an **open-source core**...` | Acceptable if the surrounding copy is fixed, but reads as the whole product being open source. |
| L34 | `self-hosting the open-source core stays free` | Core claim is true but needs Apache-2.0 qualifier to avoid confusion. |
| L53 | `**Open-source core, self-hostable**...` | Same as above. |
| L205 | `Nowing is the only product with an open-source core...` | Product-level claim; should be `open-core` or qualified. |
| L213 | `...and its core is open source.` | Less problematic, but “core is open under Apache 2.0” is clearer. |
| L231 | `Core (everything outside nowing_backend/app/proprietary/): **Apache-2.0** — truly open source.` | License table is correct; keep. |
| L247 | `**Kanban Board:** [Nowing Project Board](https://github.com/users/MODSetter/projects/3)` | Points to MODSetter’s project board. |
| L253 | `Thanks to all our Surfers:` | Inherited upstream community name (SurfSense “Surfers”); should be neutral. |

The same violations exist in the 4 translations: `README.es.md`, `README.pt-BR.md`, `README.hi.md`, `README.zh-CN.md` (grep for `MODSetter` and `open.source` confirms identical pattern at the same relative lines).

---

## 2. Proposed `NOTICE` text (applied)

`NOTICE` was created at `/Users/luisphan/Documents/GitHub/nowing/NOTICE` with the following text:

```text
Nowing
Copyright (c) Nowing

This product is a derivative of SurfSense
(https://github.com/MODSetter/SurfSense), originally developed by MODSetter.

Portions of this software are Copyright (c) SurfSense and are used under the
terms of the original SurfSense licenses:

- The SurfSense core codebase is licensed under the Apache License, Version 2.0
  (see the root LICENSE file).
- The SurfSense crawler/proprietary engine is licensed under the Business
  Source License 1.1 (see nowing_backend/app/proprietary/LICENSE).

The following Nowing components are direct directory renames of SurfSense
components:

- nowing_backend                   <- surfsense_backend
- nowing_web                       <- surfsense_web
- nowing_desktop                   <- surfsense_desktop
- nowing_browser_extension         <- surfsense_browser_extension
- nowing_obsidian                  <- surfsense_obsidian
- nowing_mcp                       <- surfsense_mcp
- nowing_evals                     <- surfsense_evals

Nowing was forked from SurfSense at commit bea603e2 (tag 0.0.34.1). A
substantial portion of the codebase remains byte-identical or substantially
derived from SurfSense at that point. Since the fork, Nowing has made
modifications and additions, including feature work in the Apache-2.0 core and
a security-related host guard in the proprietary crawler engine.

A complete file-level divergence report and the legal analysis are maintained
in:

  _bmad-output/planning-artifacts/legal/legal-brief-upstream-attribution-2026-07-26.md
  _bmad-output/planning-artifacts/legal-package-prep-2026-08-04.md
```

**Rationale:** This satisfies the Apache-2.0 §4(d) NOTICE requirement and is a best-practice attribution statement. It is not a substitute for counsel’s review of the underlying license issues.

---

## 3. Proposed `LICENSE` / `nowing_backend/app/proprietary/LICENSE` changes

### 3.1 Root `LICENSE` — high-confidence change

The upstream copyright line was replaced. Apache-2.0 §4(c) requires retention of copyright notices. The recommended change is to add the upstream copyright and a short attribution note, not to remove the Nowing copyright.

**Proposed `diff` (excerpt, first 12 lines):**

```diff
--- a/LICENSE
+++ b/LICENSE
@@ -1,7 +1,12 @@
-Copyright (c) Nowing
+Copyright (c) Nowing
+Copyright (c) SurfSense
+
+This product is a derivative of SurfSense
+(https://github.com/MODSetter/SurfSense). The original SurfSense copyright
+and dual-license notices are preserved below.
 
 Portions of this software are licensed as follows:
 
 * All content that resides under the "nowing_backend/app/proprietary/"
   directory of this repository is licensed under the Business Source License
   1.1 as defined in "nowing_backend/app/proprietary/LICENSE".
```

**Recommendation:** Apply this change. It is a straightforward attribution fix and is very likely required by Apache-2.0 §4(c). Counsel should confirm the exact form.

### 3.2 `nowing_backend/app/proprietary/LICENSE` — legal-risk change, needs counsel

This file is 85.7% byte-identical to SurfSense at the fork point. The `Licensor` and copyright line were changed from SurfSense to Nowing. This is the issue the GTM review called a potential attribution/license-misrepresentation claim (`review-gtm-business-plan-nowing-2026-08-04.md` §4, §7, §Q1).

We are **not** certain whether a derivative distributor may re-parameterize the BSL with itself as Licensor, so we provide options rather than applying a change.

#### Option A — Keep Nowing as product name, restore SurfSense as author/licensor

```diff
--- a/nowing_backend/app/proprietary/LICENSE
+++ b/nowing_backend/app/proprietary/LICENSE
@@ -7,12 +7,12 @@
 
 Parameters
 
-Licensor:             Nowing
+Licensor:             SurfSense
 
 Licensed Work:        The Nowing Proprietary Components, being all files
                       contained in this directory tree
                       (nowing_backend/app/proprietary/**).
-                      The Licensed Work is (c) 2026 Nowing.
+                      The Licensed Work is (c) 2026 SurfSense.
```

This restores the original BSL Licensor/copyright and only changes the directory path (which is a mechanical rename of the inherited tree). It is the most defensible from an authorship perspective.

#### Option B — Same as A, but add a parenthetical about Nowing modifications

```diff
--- a/nowing_backend/app/proprietary/LICENSE
+++ b/nowing_backend/app/proprietary/LICENSE
@@ -7,12 +7,13 @@
 
 Parameters
 
-Licensor:             Nowing
+Licensor:             SurfSense
 
-Licensed Work:        The Nowing Proprietary Components, being all files
+Licensed Work:        The Nowing Proprietary Components (a derivative of the
+                      SurfSense Proprietary Components), being all files
                       contained in this directory tree
                       (nowing_backend/app/proprietary/**).
-                      The Licensed Work is (c) 2026 Nowing.
+                      The Licensed Work is (c) 2026 SurfSense,
+                      with modifications (c) 2026 Nowing.
```

This is more explicit, but it may be read as modifying the BSL parameterization beyond the allowed fields. Counsel should review whether the extra text is permitted under the BSL “Covenants of Licensor.”

#### Option C — Radical / safe path

Remove or completely rewrite the inherited `nowing_backend/app/proprietary/` crawler engine before any public release. This is the highest engineering cost but the lowest legal risk.

**Recommendation:**

1. **Do not publish with `Licensor: Nowing`.** The 85.7% inherited code, the 100% directory-rename relationship, and the absence of a `NOTICE` file make this an indefensible authorship claim.
2. **Prefer Option A** as the minimal legal correction, with the new `NOTICE` file explaining Nowing’s modifications.
3. **Ask counsel:** whether a downstream distributor can validly be the BSL `Licensor` for an 85.7% inherited work, and whether the `Change Date` should restart from Nowing’s public release or from SurfSense’s original release.
4. If counsel says the inherited BSL code cannot be distributed under a Nowing-branded BSL at all, fall back to **Option C**.

---

## 4. Proposed `README.md` changes

### 4.1 “Open source” messaging

The product is **not** entirely open source; only the core is Apache-2.0. The crawler engine is BSL 1.1 (which explicitly says it is **not** an open-source license), and the deep-research engine is closed-source/hosted.

**Proposed line-level changes (table, not applied):**

| Line | Current | Proposed |
|---|---|---|
| L1 | `alt="Nowing — open-source AI research workspace..."` | `alt="Nowing — open-core AI research workspace..."` |
| L20 | `<a href="https://trendshift.io/repositories/13606"... alt="MODSetter%2FNowing \| Trendshift"...` | **Remove** or replace with a Nowing-specific Trendshift URL and `alt="Nowing \| Trendshift"`. If no Nowing Trendshift page exists yet, remove the block. |
| L23 | `# Nowing: Open-Source Research Memory for AI Agents` | `# Nowing: Open-Core Research Memory for AI Agents` |
| L25 | `> **Nowing is open-source research memory...**` | `> **Nowing is research memory for AI agents — it remembers what it went and found, not just what you told it.**` |
| L27 | `powered by an **open-source core** and a **hosted deep-research engine**` | `powered by an **Apache-2.0 open-source core**, a **BSL 1.1 crawler engine**, and a **hosted deep-research engine**` |
| L34 | `self-hosting the open-source core stays free` | `self-hosting the Apache-2.0 core stays free` |
| L53 | `**Open-source core, self-hostable**` | `**Apache-2.0 core, self-hostable**` |
| L205 | `Nowing is the only product with an open-source core that combines...` | `Nowing is the only product with an **open-core** (Apache-2.0 + BSL 1.1) research workspace that combines...` |
| L213 | `...and its core is open source.` | `...and its core is open under Apache 2.0.` |
| L231 | `Core ... Apache-2.0 — truly open source.` | Keep (license table is correct). |
| L247 | `**Kanban Board:** [Nowing Project Board](https://github.com/users/MODSetter/projects/3)` | **Remove** or replace with a Nowing-owned project board URL. If none exists, remove. |
| L253 | `Thanks to all our Surfers:` | `Thanks to all our contributors:` |

### 4.2 Translations

The same replacements apply to:

- `README.es.md`
- `README.pt-BR.md`
- `README.hi.md`
- `README.zh-CN.md`

Grep output shows identical `MODSetter` badge and project-board links and the same `open source` wording in each translation.

### 4.3 Rationale

- `brief-Nowing-2026-07-25/brief.md` §7 (do-say / don’t-say table) explicitly says: **“Apache-2.0 core + BSL 1.1 crawler engine” — say the two licenses; do NOT call the whole product “open source.”**
- `review-gtm-business-plan-nowing-2026-08-04.md` §9 (Messaging) rates this **Critical (launch-blocking)** and lists the `README.md` lines above as violations.
- The MODSetter badge/project-board links are also called out in the legal brief §2.5 as upstream-author assets labeled with the Nowing product name.

**Recommendation:** Apply the README messaging changes immediately (they are factual, not legal). Do **not** apply the `LICENSE`/`proprietary/LICENSE` changes until counsel reviews.

---

## 5. Open questions for counsel

1. **Apache-2.0 §4(c) and §4(d):** Is the new `NOTICE` file sufficient, or must the upstream `Copyright (c) SurfSense` line also appear in the Apache-2.0 `LICENSE` header or in a separate `NOTICE` file? Does upstream’s lack of a `NOTICE` file reduce the attribution obligation?
2. **Apache-2.0 §4(b):** 272 modified files currently carry no prominent notice of change. Is repository-level attribution via `NOTICE`/`LICENSE` sufficient, or must each modified file contain a change notice?
3. **BSL Licensor issue:** Can a downstream distributor of an 85.7% inherited BSL work lawfully name itself as the BSL `Licensor` and `copyright` holder, or must it retain the upstream entity? Does the surfacing of one functional change (`url_resolver.py`) affect the answer?
4. **BSL Additional Use Grant:** Does the planned Nowing cloud hosted service “derive, entirely or substantially” value from the inherited BSL crawler engine, and does the architectural separation (engine called over HTTP by a separate closed-source service) matter? (`legal-brief-upstream-attribution-2026-07-26.md` §6, Q3)
5. **Pre-publication requirements:** What is the minimum package (`NOTICE`, `LICENSE` correction, per-file notices, upstream notification, consent) required before the repository can be made public?
6. **Internal-use exposure:** The repository has been run internally and developed against, but not published. Have any license obligations already been triggered by internal deployment or by production use, even without distribution?
7. **Added files / authorship:** The 111 new `.py` files in the Apache-2.0 core and the 16 new `.py` files in the BSL directory are Nowing-authored. Does Nowing have a valid copyright in those additions, and do they affect the overall percentage or licensing of the inherited components?
8. **Marketing copy exposure:** Does the current public-facing website copy that calls the product “open source” (e.g. `nowing_web/components/pricing/pricing-section.tsx`, `nowing_web/app/(home)/free/page.tsx` per `review-gtm-business-plan` §9) create separate misrepresentation/attribution exposure beyond the repo license terms?

---

## 6. Files touched / reviewed

### 6.1 Created

- `/Users/luisphan/Documents/GitHub/nowing/NOTICE`
- `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/legal-package-prep-2026-08-04.md`

### 6.2 Reviewed (not modified)

- `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/legal/legal-brief-upstream-attribution-2026-07-26.md`
- `/Users/luisphan/Documents/GitHub/nowing/LICENSE`
- `/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/proprietary/LICENSE`
- `/Users/luisphan/Documents/GitHub/nowing/README.md`
- `/Users/luisphan/Documents/GitHub/nowing/README.es.md`
- `/Users/luisphan/Documents/GitHub/nowing/README.pt-BR.md`
- `/Users/luisphan/Documents/GitHub/nowing/README.hi.md`
- `/Users/luisphan/Documents/GitHub/nowing/README.zh-CN.md`
- `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/briefs/brief-Nowing-2026-07-25/brief.md`
- `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md`
- `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/review-gtm-business-plan-nowing-2026-08-04.md`

### 6.3 Commands used to verify figures

- `git remote -v`
- `git merge-base HEAD upstream/main`
- `git describe --tags bea603e2253989970389eb26db56406c4070500c`
- `git rev-list --count bea603e2...`
- `git rev-list --count bea603e2...HEAD`
- `git show bea603e2:LICENSE` and `...:surfsense_backend/app/proprietary/LICENSE`
- `git archive ...` + Python divergence script (`/tmp/legal-check/divergence2.py`) for Apache-2.0 core
- Custom BSL divergence scripts for `nowing_backend/app/proprietary/**/*.py`
- `grep` for `open.source`, `MODSetter`, `trendshift`, `Project Board`, `Surfers` across `README*.md`
- `find nowing_backend/app -name '*.py' | wc -l` and similar counts

No commits or pushes were made.
