# Review — GTM & Business Plan (Nowing)

**Review target:** `gtm-business-plan-nowing-2026-08-04.md`  
**Reviewer lens:** strategic, adversarial, execution-oriented  
**Date:** 2026-08-04

---

## 1. Overall Verdict

**Weak / Unacceptable for public launch as-is.**

The plan is directionally coherent: an open-core, self-host-first PLG wedge with a usage-based cloud tier and an enterprise track is a defensible playbook for a research-memory product. However, the plan treats several high-uncertainty, high-exposure items as already solved when the repository shows they are not. The most important blockers are legal/attribution (the inherited SurfSense code cannot be publicly released in its current license state), product/UX (deep-research degradation is hidden from the user), and economics (deep-research unit cost is not fully loaded and no public price exists for it). The financial model and market sizing are also more aspirational than evidence-based. **Do not approve this plan for a “Show HN” or public repo launch until the five red flags below are resolved.**

> **Callout tiếng Việt:** *Kế hoạch không thể được phê duyệt để ra mắt công chúng cho đến khi 5 lá cờ đỏ pháp lý, kỹ thuật, tài chính, messaging và product-market gating được xử lý triệt để.*

---

## 2. Dimension-by-Dimension Review

### 1. Strategic Coherence
**Rating: Adequate**

- **What works:** Open-core PLG + usage-based cloud + enterprise is a logical fit for a developer-facing, self-hostable product. The sequencing (self-host/community → cloud revenue → enterprise) is plausible if the product can build trust through transparent code and then convert power users to managed deep research.
- **What weakens it:** The strategy depends on being able to call the repository “open source” and on the BSL crawler engine being a defensible moat. Both are factually fragile right now (`app/proprietary/` is 87% byte-identical to SurfSense, `LICENSE`/`app/proprietary/LICENSE` replace the upstream copyright holder, and public copy repeatedly says “open source” for the whole product).
- **Recommendation:** Reframe the strategic narrative from “open-source product” to “open-core product with a hosted deep-research engine and a BSL crawler engine.” Do not make open-source identity the central wedge until legal counsel clears the fork.

> **Callout tiếng Việt:** *Chiến lược đúng hướng, nhưng bản lĩnh dựa trên “open source” và BSL moat đang bị lung lay bởi vấn đề attribution — cần tái định vị trước khi ra mắt.*

---

### 2. Market Sizing Sanity
**Rating: Weak**

- **TAM ($12–15B):** Reasonable as a top-down AI memory / agentic research market estimate, but the plan provides no source, no growth rate, and no segmentation between research-memory, RAG, and general agent infrastructure.
- **SAM ($2.0–2.8B):** Derived from a vague “technical/research teams in mid-market + enterprise,” not from a bottoms-up calculation of workspaces, seats, or ARPU.
- **SOM ($10–30M ARR in 12–18 months):** Requires 10k–30k self-hosted installs converting at 0.5–3% and ARPU of $100–$800. There is no evidence that Nowing’s distribution channels (GitHub, MCP, HN) can drive that install base without paid, push, or partner GTM. The 0.5–3% conversion benchmark is a generic OSS conversion range; it is not validated for a Vietnam-rooted, research-memory product with a cloud deep-research dependency.
- **ARPU assumption ($100–$800/mo):** The high end is plausible only for enterprise; the low end is contradicted by the pay-as-you-go FAQ, which implies users top up small credit balances. A $100/mo minimum requires either per-seat pricing or heavy deep-research usage, neither of which is modeled.
- **Recommendation:** Build a bottoms-up SOM model from (a) expected GitHub stars/HN traffic, (b) MCP install base, (c) deep-research call volume per paying team, and (d) a real per-call price. Until then, treat the SOM as an aspiration, not a forecast.

---

### 3. Competitive Positioning
**Rating: Adequate**

- **The wedge is clear:** “Live web + UGC into self-hosted long-term memory with provenance” is a differentiated story compared to NotebookLM (file-centric), Perplexity (search/answer), and Mem0 (state-only memory).
- **Durability is unproven:** The strongest differentiator in the brief — “memory tự re-validate nguồn” — is blocked by the `Memory.source_id` / `Run.id` type mismatch and the 30-day `RUNS_RETENTION_DAYS` cleanup (`PRD §4.9 FR-39`, `app/db.py:2077`, `app/capabilities/core/runs.py:33`). Story `9.6a/9.6b` is still open. If this is the moat, the plan should not assume it is already built.
- **Incumbents can fast-follow:** Google (NotebookLM, Search, Maps) and Perplexity have distribution, existing web crawlers, and API relationships. They can add persistent research threads and multi-source live web in 6–12 months.
- **Recommendation:** Make provenance/re-validation a P0 fast-follow after launch, not a Phase 2 enterprise feature, and prepare an anti- incumbent narrative.

---

### 4. Business Model & Pricing
**Rating: Weak**

- **License model is conceptually sound but legally exposed:** Apache-2.0 core + BSL 1.1 crawler engine + closed deep-research engine is a defensible tri-tier. However, the BSL `Licensor: Nowing` is applied to code that is 87% inherited from SurfSense with no `NOTICE` file (`legal-brief-upstream-attribution-2026-07-26.md` §2.3–2.5, `nowing_backend/app/proprietary/LICENSE:10-15`). This could invalidate the moat and expose the company to attribution / license misrepresentation claims.
- **Margin target (1.5–2.5×) is not grounded:** The plan does not quantify the Nowing-side cost of a deep-research call. ChainLens research `balanced` costs $0.0482/call (`report-per-mode.md` cited in `9-2-deep-research-cost-metering.md:39-52`), but the 9.2 artifact notes that full-pipeline cost at ChainLens is expected to be **1.5–2.5×** the writer cost and “Pricing/margin cần để lại dự phòng” (`9-2-deep-research-cost-metering.md:152-153`). On top of that, Nowing adds orchestrator LLM calls, KB fallback search, embedding, and infra. The plan does not include these in the margin math.
- **No public deep-research price:** The pricing page (`nowing_web/components/pricing/pricing-section.tsx:32-74`) lists pay-as-you-go credit, scraper/crawl per-item pricing, and premium models at “provider cost,” but never lists a deep-research per-call or per-mode price. This is a critical gap because deep research is the cloud-only capability meant to convert self-hosters.
- **Recommendation:** Freeze public pricing until SM-11a (real per-mode cost) and NFR-9 (latency/cost gating) are ratified. Build a fully-loaded unit cost model that includes ChainLens, Nowing orchestrator, KB fallback, and infra before committing to ARPU.

> **Callout tiếng Việt:** *Mô hình giá chưa có cơ sở chi phí thật: deep-research mới chỉ biết cost ChainLens, chưa tính LLM orchestrator, fallback KB, infra; chưa có giá public cho deep research.*

---

### 5. GTM Motion Feasibility
**Rating: Weak**

- **Distribution is too narrow:** The plan relies on GitHub, Hacker News, MCP server, and organic word-of-mouth. There is no SEO content engine, no paid experiments, no integration marketplace, no vertical partnerships, and no community-led event strategy. For a product targeting research teams, this is insufficient to reach 10k–30k installs in 12–18 months.
- **“Dev-strong, GTM-thin” is a real constraint:** The plan acknowledges this but does not offer a concrete GTM hire or agency plan to close the gap.
- **MCP is a good distribution hack but not a funnel:** Being an MCP server helps developers try the product, but it does not explain why a team would move from a free self-host to a paid cloud.
- **Recommendation:** Add at least one push channel (e.g., vertical influencer/programmatic SEO around “Reddit/YouTube research API,” or a small paid retargeting budget) and define the conversion path from MCP/self-host to cloud.

---

### 6. Execution Roadmap & Gates
**Rating: Weak**

- **Gate order is partly wrong:** The plan lists `NFR-8 → FR-38 → FR-37 → 8.7`. The correct dependency is closer to `9.1a (degradation) → 9.1b (contract) → 9.2 (cost) → 8.7 (auto-extract cap) → 9.3 (latency/state A→B) → NFR-8 ratification (SM-10) → pricing`. The plan also omits `3-14` (bounded memory injection / score exposure), which is a prerequisite for a valid SM-10 baseline.
- **NFR-8 is not closed:** The eval gate exists and a live run artifact from 2026-07-28 shows strong numbers (recall@5 0.986, mrr 1.0, distractor noise 0.067, off-corpus 0.033 — `evidence/3-14-eval-20260728T230000Z/memory/runs/2026-07-28T16-28-54Z/recall/run_artifact.json:59-91`), but `nowing_evals/src/nowing_evals/suites/memory/recall/gate.yaml:60` still has `baseline_ratified: false`. The gate is explicitly designed to **fail closed** until the metric owner signs off (`3-9-memory-recall-eval-gate.md:104`).
- **NFR-9 State B is not reached:** ChainLens 2026-08-02 benchmark shows `balanced` p95 at **44.3s**, exceeding the 30s target (`prd-Nowing-2026-07-22/prd.md:835`). The product must therefore remain in State A (async deliverable) at launch. The plan should not assume synchronous “deep research in chat” is available.
- **FR-38 / FR-37 are done in code but not in UX:** The executor now degrades to `engine_unavailable` / `partial` and parses `costDollars` (`app/capabilities/chainlens/research/executor.py:369-425`, `app/capabilities/core/billing.py:253-318`), but the timeline UI does not surface degradation status (see Red Flag #2).
- **8.7 is done but disabled by default:** The auto-extract budget/rate-limit gate is implemented (`app/services/memory/extraction.py:172-176`, `app/services/memory/extract_budget.py`), but the budget cap defaults to `0` (disabled) because the cost baseline is not ratified (`8-7-auto-extract-spend-budget-cap.md:100`).
- **Recommendation:** Rewrite the roadmap as a gantt of hard gates with pass/fail evidence, not as a list of story numbers. Do not launch until NFR-8 is ratified and NFR-9 State A is explicitly the launch default.

---

### 7. Risks & Mitigations
**Rating: Adequate**

- **What is present:** Legal attribution, ChainLens dependency, and market timing are listed.
- **What is under-mitigated:**
  - The legal risk is listed but the mitigation is “consult counsel.” It should be a launch-blocking milestone with concrete deliverables.
  - The ChainLens risk is underweighted: the plan does not specify a latency/cost SLA, a contract-escape clause, or a fallback if ChainLens stops supporting Nowing.
  - The “incumbent fast-follow” risk lacks a product response beyond “ship faster.”
- **Recommendation:** Convert the legal item into a P0 launch gate; add a ChainLens risk register with monthly cost/latency review; add a “defensible differentiation” workstream (provenance/re-validation).

---

### 8. Metrics
**Rating: Adequate**

- **Metrics are well-chosen:** SM-1 (active workspaces), SM-10 (recall quality), SM-11a/b/c (deep-research cost/latency/fallback) are the right leading/lagging indicators.
- **Gaps:**
  - **SM-10 not ratified** (`gate.yaml:60`).
  - **SM-11b shows State B is not viable yet** (`prd.md:835`).
  - **SM-11a cost basis** is not fully loaded (9.2 open question).
  - No conversion metric from self-host to cloud is defined.
- **Recommendation:** Add `SM-12: self-host → cloud conversion rate` and `SM-13: deep-research call volume per paying workspace`. Ratify SM-10 and SM-11 before any paid launch.

---

### 9. Messaging
**Rating: Critical (launch-blocking)**

- The brief’s “do say / don’t say” table is clear: do not call the whole product “open source,” do not call it a “NotebookLM alternative,” and do not mention ChainLens (`brief-Nowing-2026-07-25/brief.md:251-268`).
- Public assets still violate all three rules:
  - `README.md:1` alt text and `README.md:25` call the product “open-source research memory.”
  - `nowing_web/components/pricing/pricing-section.tsx:183` FAQ says “Yes. Nowing is open source…”
  - `nowing_web/app/(home)/free/page.tsx:142` and `:147` call Nowing a “free ChatGPT alternative” and a “free, open source alternative to ChatGPT.”
  - `nowing_web/changelog/content/2026-07-05.mdx:13` and `:17` call Nowing the “open-source alternative to NotebookLM.”
  - `nowing_web/components/homepage/social-proof.tsx:35-83` is filled with “Nowing vs NotebookLM” / “NotebookLM Is Great… Until You See Nowing” / “¿Superaron a NotebookLM?” titles.
  - `nowing_web/components/homepage/hero-section.tsx:658`, `content/docs/index.mdx:10`, `components/seo/json-ld.tsx:22-79` all repeat “open-source research memory.”
- **Recommendation:** Run `scripts/check-docs-drift.py` and a manual messaging audit before any public release. The current public copy will attract license flame and HN/Reddit backlash.

> **Callout tiếng Việt:** *Messaging hiện tại vi phạm trầm trọng bảng NÓI/KHÔNG NÓI: còn “open source” cho cả sản phẩm, “NotebookLM alternative”, “ChatGPT alternative”; đây là rủi ro pháp lý và reputational trước khi ra mắt.*

---

### 10. Actionability
**Rating: Weak**

- **Engineering can act on some items tomorrow:** The product is mostly built, CI exists, and stories are well-specified.
- **The plan is not actionable because several gates are undefined:**
  - “Get legal clearance” has no exit criteria.
  - “Set pricing” is blocked on cost numbers that are not measured.
  - “Launch Show HN” is blocked on messaging cleanup that is not itemized.
  - The enterprise/Phase 3 playbook is vague.
- **Recommendation:** Convert the plan into a launch readiness checklist with owners, evidence files, and go/no-go dates.

---

## 3. Answers to Specific Questions

### Q1: What is the single biggest unstated assumption that could invalidate this plan?

There are two equally dangerous unstated assumptions; the legal one is the most likely to kill the launch.

1. **Legal/IP assumption:** That Nowing can legally call itself the licensor of `app/proprietary/` and publicly release the repository without a `NOTICE` file or SurfSense attribution. Evidence to disprove it: an external counsel opinion, or an upstream DMCA/attribution complaint. The legal brief already flags this as blocking public repo (`legal-brief-upstream-attribution-2026-07-26.md:47-55`).

2. **Technical/economic assumption:** That ChainLens `balanced` mode will hit p95 ≤ 30s at roughly the current $0.0482/call, enabling the synchronous “deep research in chat” use case and the 1.5–2.5× margin target. Evidence to disprove it: the 2026-08-02 ChainLens benchmark shows `balanced` p95 at **44.3s** (`prd.md:835`), and the full-pipeline cost is expected to be **1.5–2.5×** higher (`9-2:152-153`).

> **Callout tiếng Việt:** *Giả định ngầm lớn nhất: (1) pháp lý cho phép tự xưng là Licensor trên code kế thừa; (2) ChainLens latency/cost sẽ đủ tốt để mở State B. Cả hai đều chưa có bằng chứng.*

---

### Q2: Where is the plan most vulnerable to an incumbent’s fast follow?

**Vulnerability: Google NotebookLM / Google Search / Google Maps ecosystem.**

NotebookLM already owns the file-centric, long-context research workspace. Google has YouTube, Google Search, Maps, and a massive API infrastructure. A plausible 6-month response:

- **Month 1–2:** Add live web snippets (Reddit, YouTube, Maps) to NotebookLM via Google Search / Knowledge Graph.
- **Month 2–4:** Add “Research Threads” — persistent, shareable, multi-turn research sessions with citations.
- **Month 4–5:** Add team workspaces and scheduled research briefs.
- **Month 5–6:** Bundle with Google Workspace / AI Premium and undercut on distribution by offering a free tier to every Google account.

**Why it hurts Nowing:** Nowing’s advantage (self-host + open-core + live web) becomes a niche differentiator if Google makes the cloud alternative free, frictionless, and already integrated with Drive/YouTube/Maps.

**Mitigation:** Nowing must lean into **self-host / data-control / anti-lock-in** and **provenance/re-validation** (FR-39) faster than Google can copy. It also needs a B2B team/collaboration story that Google’s consumer-first products will not prioritize.

---

### Q3: Is the pricing model likely to produce positive gross margin?

**Not yet — the unit economics are incomplete.**

#### One typical cloud deep-research call

| Cost component | Low estimate | Mid estimate | Source |
|---|---|---|---|
| ChainLens `balanced` research call | $0.0482 | $0.0482 | `9-2-deep-research-cost-metering.md:49` |
| ChainLens full-pipeline overhead (1.5–2.5×) | +$0.024–0.072 | +$0.048 | `9-2:152-153` |
| Nowing orchestrator LLM / KB fallback / embedding | +$0.01–0.03 | +$0.02 | Inferred from agent/tool flow |
| Infra / observability / billing per call | +$0.005–0.02 | +$0.01 | Inferred |
| **Fully-loaded cost per call** | **~$0.09** | **~$0.12** | |

At a 1.5–2.5× margin, the customer price should be **$0.13–$0.30 per call**. But:

- The pricing page does not list a deep-research per-call price (`pricing-section.tsx:32-74`).
- The FAQ says premium models are billed at “provider cost,” which implies **zero markup** on LLM usage — directly contradictory to a margin target.
- If deep research is priced at provider cost or included in a flat credit balance, gross margin is negative or near zero.

#### One typical active research team per month

Assume a 4-user team, 20 working days, 10 deep-research calls per user per day = 800 calls/month.

- At $0.12 cost and $0.20 price: revenue $160, COGS $96, gross $64. ARPU per user = **$40** — far below the $100–$800 target.
- To hit $400 ARPU on deep research alone at $0.20/call, the team must make **2,000 calls/user/month**, which is unrealistic.
- The $100–$800 ARPU only works if the plan adds (a) per-seat fees, (b) heavy scraper/crawl volume with markup, or (c) enterprise add-ons — none of which are modeled.

**Conclusion:** Positive gross margin is **possible but not proven**. The plan must first close the fully-loaded cost at ChainLens and Nowing, then set explicit per-mode pricing, and only then validate ARPU.

> **Callout tiếng Việt:** *Margin dương chưa được chứng minh: chưa có giá public cho deep research, chưa tính đủ chi phí Nowing-side, ARPU $100–$800 không khớp với mô hình pay-per-call hiện tại.*

---

### Q4: What would make self-hosters convert to cloud? Is deep research alone enough?

**Deep research alone is not enough.** Self-hosters are, by definition, willing to operate infrastructure. A cloud-only API call is not a strong conversion lever unless it is dramatically cheaper/easier than self-hosting the same capability.

**Conversion levers that should be added earlier (Phase 1, not Phase 3):**

1. **Cloud-only collaboration:** multi-workspace sharing, team permissions, shared research threads, and audit logs. Self-hosting can do this, but it requires setup; cloud removes ops friction.
2. **Managed connectors:** anti-bot/CAPTCHA infrastructure for Reddit/YouTube/Amazon requires proxy rotation, session warming, and legal risk. Cloud can absorb that.
3. **Centralized billing & cost observability:** The credit wallet and usage dashboard (NFR-7/FR-31) should be cloud-only and clearly superior to self-hosted opaque billing.
4. **Real-time deliverables & notifications:** Async deep research with `Report` persistence and notifications (`app/capabilities/core/async_runner.py:238`, `app/routes/admin_latency_routes.py`) is a cloud UX win.
5. **Compliance / retention / right-to-delete:** OQ-3 legal risks are easier to manage in cloud.

**Recommendation:** Add a “Team Cloud” tier in Phase 1, positioned as “self-host your core data, but run heavy/deep research and team features in our cloud.”

---

### Q5: Should the plan sequence cloud-first or self-host-first differently?

**Keep self-host-first for PLG, but run cloud in parallel — and do not open the public repo until legal is clean.**

- **Self-host-first is correct for this product** because:
  - It builds trust with data-sensitive research teams.
  - It creates a natural GitHub/MCP distribution channel.
  - It aligns with the open-core license story.
- **Cloud-first for revenue is also correct** because:
  - Deep research is cloud-only in Phase 1 (FR-38).
  - Managed infrastructure is the fastest path to ARPU.
  - The “try cloud, then self-host, then hybrid” funnel is a cleaner enterprise motion.
- **The plan’s flaw is timing:** it implies waiting 12–18 months for meaningful cloud revenue. That is too long for a product whose main differentiator (deep research) is hosted. Cloud sign-up should be available at public launch, not delayed.
- **The bigger sequencing flaw is legal:** the public repo cannot be released before the SurfSense attribution/L-1 gate closes, regardless of self-host or cloud.

**Recommendation:** Revise Phase 1 to “public repo (after legal) + cloud pay-as-you-go live on day one,” with self-host as the viral top-of-funnel and cloud as the monetization path.

---

### Q6: What is the minimum viable “Show HN” launch?

A launch is not a single artifact; it is a set of pass/fail quality bars. The minimum viable “Show HN” bundle:

| Artifact | Quality bar |
|---|---|
| **README.md** | Apache-2.0 + BSL 1.1 phrasing; no “open-source research memory” for the whole product; clear self-host vs cloud table; `NOTICE` file and SurfSense attribution; no `MODSetter` badge/project-board (`README.md:1`, `:20`, `:25`, `:255`). |
| **LICENSE / `app/proprietary/LICENSE`** | Licensor / copyright aligned with counsel’s opinion; `NOTICE` file present. |
| **Landing page (`nowing_web/app/(home)`, `components/homepage`)** | Single promise from brief §1; no NotebookLM/ChatGPT comparisons; no “open source” for whole product; deep research described as “hosted, cloud” not synchronous. |
| **Pricing page** | Deep-research per-call/per-mode pricing listed; no “provider cost = no markup” contradiction; self-host FAQ corrected to “open-core,” not “open source and unlimited.” |
| **Docker / `.env.example`** | `CHAINLENS_API_KEY` empty is valid; deep research degrades to KB; no engine setup required (`nowing_backend/.env.example:718-724`). |
| **MCP server** | `nowing_mcp/mcp_server/selfcheck.py` passes; `nowing_recall` and `nowing_chainlens_research` tools stable. |
| **Demo** | < 2-minute video showing self-host install, KB upload, async deep-research request, and `engine_unavailable` degradation path. |
| **CI / gates** | `memory-recall-release-gate.yml` passes with `baseline_ratified: true`; NFR-9 State A only; no State B claims. |
| **Legal** | External counsel sign-off on attribution and BSL licensor. |

> **Callout tiếng Việt:** *“Show HN” tối thiểu không chỉ là code chạy; nó cần messaging sạch, legal dứt khoát, README đúng, và UI thể hiện rõ degradation.*

---

### Q7: Where does the plan over-rely on ChainLens?

**ChainLens is a single-point-of-failure for the cloud differentiator.**

- **Cost:** Nowing cannot set reliable pricing until ChainLens exposes stable `costDollars` and the full-pipeline cost lands. 9.2 notes this is **2–4 sprints away** (`9-2:152-153`).
- **Latency / UX:** NFR-9 State B (sync chat-mode) is gated on ChainLens Epic 43 (`43-1` eval harness, `43-2` planner-DAG, `43-5` cache). The 2026-08-02 benchmark shows `balanced` p95 is still 44.3s (`prd.md:835`), so State B is not viable at launch.
- **Contract / uptime:** The parser, progress events, and `costDollars` shape are all ChainLens-defined. A breaking change on the engine side can break Nowing’s billing and UX.
- **Commercial risk:** ChainLens is a separate, closed-source entity. If it raises prices, changes terms, or deprioritizes Nowing, the cloud business model changes overnight.

**Mitigations already in place:**
- FR-38 degradation to KB fallback (`app/capabilities/chainlens/research/executor.py:207-275`).
- 9.1b contract regression guard and SSE golden fixture.
- 9.2 real cost metering and fallback flat-rate.
- 9.3 latency measurement (`TokenUsage.e2e_ms` / `ttfb_ms`, `app/routes/admin_latency_routes.py`).

**Additional mitigations needed:**
- A written ChainLens SLA or at minimum a commercial agreement with price-change notification.
- A “mode policy” in Nowing that defaults to the cheapest mode (`balanced`) and refuses `quality` for routine queries (`app/config/__init__.py:970` already does this; document it in pricing).
- A public statement that deep research is **cloud-only and async at launch**, so users do not expect synchronous behavior.

---

### Q8: Are there missing non-goals or anti-goals?

Yes. The plan should explicitly add:

1. **Do not call Nowing “open source” as a whole product until legal counsel clears the fork and a `NOTICE` file is in place.** This is an anti-goal that should be written in the plan, not just in the brief.
2. **Do not position against “ChatGPT” or “NotebookLM.”** These comparisons are in the current landing/changelog and invite incumbent retaliation while diluting the research-memory wedge.
3. **Do not allow self-host → ChainLens direct calls.** Phase 2 must route through Nowing Cloud API, not the engine, to preserve the single-consumer contract (`PRD §4.9 FR-38`, `epics.md:731-750`).
4. **Do not set public pricing before SM-11a and NFR-9 are ratified.** The PRD already has this gate; the business plan should enforce it.
5. **Do not launch the public repo before L-1 closes.** This should be the first non-goal in the launch section.

---

## 4. Top 5 Action Items (prioritized)

1. **Close legal/attribution gate L-1 before any public release.**
   - Deliverables: external counsel opinion; `NOTICE` file; corrected `LICENSE` / `app/proprietary/LICENSE`; README/landing attribution; removal of `MODSetter` badge/project-board remnants.
   - Owner: Founder + Legal.
   - Launch-blocking: **yes**.

2. **Fix deep-research degradation UX in chat timeline.**
   - Build a dedicated `chainlens.research` timeline body (or extend `FallbackToolBody`) that reads `ResearchOutput.status`, `degraded`, `degradation_reason`, and `next_action` and renders `engine_unavailable` / `partial` / `insufficient_evidence` with human-readable guidance.
   - Stop the timeline header from saying “Reviewed” when a deep-research step returns degraded (`nowing_web/features/chat-messages/timeline/timeline.tsx:91-97`).
   - Owner: Frontend / product.

3. **Ratify SM-10 and make NFR-8 a hard launch gate.**
   - Run `nowing_evals` on a live, dedicated workspace with a real corpus, set `baseline_source` and `baseline_ratified: true` in `gate.yaml:60`, and require a non-zero exit from the release gate before launch.
   - Owner: ML/Search lead.

4. **Lock deep-research unit economics and pricing.**
   - Measure Nowing-side cost (orchestrator LLM, KB fallback, embedding, infra) per mode.
   - Get ChainLens full-pipeline cost figure (1.5–2.5× story).
   - Set public per-mode price only after fully-loaded cost is known and margin target is achievable.
   - Owner: Product + Finance.

5. **Audit and clean all public messaging against the brief’s “do say / don’t say” table.**
   - Files to fix: `README.md`, `nowing_web/components/pricing/pricing-section.tsx`, `nowing_web/app/(home)/free/page.tsx`, `nowing_web/changelog/content/2026-07-05.mdx`, `nowing_web/components/homepage/hero-section.tsx`, `nowing_web/components/homepage/social-proof.tsx`, `nowing_web/content/docs/index.mdx`, `components/seo/json-ld.tsx`.
   - Run `scripts/check-docs-drift.py` and a manual pass.
   - Owner: Growth / copy.

---

## 5. Red Flags — Must Fix Before Approval

### Red Flag 1: Legal gate L-1 is open; public repo is blocked
- `LICENSE:1` claims `Copyright (c) Nowing` while the whole repo is a fork of SurfSense (`legal-brief-upstream-attribution-2026-07-26.md:62-87`).
- `nowing_backend/app/proprietary/LICENSE:10` and `:15` list `Licensor: Nowing` and `(c) 2026 Nowing` on code that is 87% byte-identical to SurfSense (`legal-brief:104-111`).
- No `NOTICE` file exists anywhere in the repository.
- README still has legacy `MODSetter%2FNowing` badge and a project board link to `github.com/users/MODSetter/projects/3` (`README.md:20`, `:255`).
- **Impact:** Public release in the current state risks license misrepresentation, DMCA/attribution disputes, and HN backlash. This is a hard stop.

> **Callout tiếng Việt:** *Cổng pháp lý L-1 chưa đóng: thiếu NOTICE, Licensor sai trên code kế thừa, README còn link/badge của upstream. Không thể public repo.*

### Red Flag 2: Conversion lever broken — UI silently labels degraded deep research as “Reviewed”
- `nowing_backend/app/capabilities/core/access/agent.py:145-179` makes deep research async and returns `{"run_id": ..., "status": "running"}`. The chat turn ends without the actual result.
- `nowing_web/features/chat-messages/timeline/timeline.tsx:91-97` shows the header **“Reviewed”** whenever all timeline items are settled (`completed/cancelled/error`).
- `nowing_web/features/chat-messages/timeline/tool-registry/fallback/default-fallback-card.tsx:61-63` only distinguishes `cancelled/error/running`; a completed tool call always renders a checkmark, regardless of the payload’s `status`.
- `nowing_web/features/chat-messages/timeline/build-timeline.ts:195-210` maps `step.status` to the item status; it does **not** inspect the tool `result.status`, `degraded`, or `next_action`.
- `nowing_web/features/chat-messages/timeline/tool-registry/registry.ts:189-223` has no component for `chainlens.research`, so it falls through to `FallbackToolBody`.
- **Impact:** A self-hosted user with no `CHAINLENS_API_KEY` will get a `ResearchOutput.status == "engine_unavailable"` from the backend, but the UI will show a green checkmark and “Reviewed.” This is a conversion and trust killer.

> **Callout tiếng Việt:** *Cần gạt đỏ: UI che trạng thái degraded `engine_unavailable`, hiển thị “Reviewed” — người dùng self-host không biết deep research không chạy.*

### Red Flag 3: Plan is out of sync with the repo
- `sprint-status.yaml` marks `3-9`, `3-14`, `8-7`, `9-1b`, `9-2`, `9-3` as `done`, but:
  - `nowing_evals/src/nowing_evals/suites/memory/recall/gate.yaml:60` still has `baseline_ratified: false`, so NFR-8 is **not** closed (`3-9-memory-recall-eval-gate.md:104`).
  - `prd.md:835` shows `balanced` p95 at **44.3s**, so NFR-9 State B is not reached.
  - `9-2-deep-research-cost-metering.md:152-153` says full-pipeline cost at ChainLens is still 1.5–2.5× away, and pricing should not be set yet.
  - `8-7-auto-extract-spend-budget-cap.md:100` says the auto-extract budget cap is `0` by default because the cost baseline is not ratified.
- **Impact:** The business plan assumes gates are closed that are still open or ratification-pending. Launching on these assumptions is risky.

### Red Flag 4: Pricing margin may be wrong because orchestrator / full-pipeline cost is missing
- ChainLens `balanced` research cost is $0.0482/call (`9-2:49`).
- ChainLens full-pipeline cost is expected to be **1.5–2.5×** the writer cost (`9-2:152-153`).
- The business plan does not account for the Nowing-side LLM orchestrator, KB fallback, embedding, token tracking, and infra per call.
- The pricing page lists no deep-research per-call price and says premium models are at “provider cost” (`pricing-section.tsx:32-74`, `:142-143`).
- **Impact:** The 1.5–2.5× margin target is not grounded. If deep research is billed at provider cost or wrapped in a flat credit model, gross margin is thin or negative.

### Red Flag 5: Sizing is unrealistic without push GTM
- The plan targets 10k–30k self-hosted installs in 12–18 months and 0.5–3% conversion.
- Channels listed are GitHub, HN, and MCP — all inbound/organic.
- There is no SEO content program, no paid acquisition, no integration marketplace, no vertical community, and no enterprise SDR motion.
- **Impact:** The SOM ($10–30M ARR) is not credible without a distribution model that can generate the top-of-funnel. The 0.5–3% benchmark is generic and not validated for this category.

### Red Flag 6: SM-10 is not actually measured/ratified
- The recall gate config has `baseline_ratified: false` (`gate.yaml:60`).
- The 3.9 story explicitly states the gate **fails closed** until baseline is ratified (`3-9-memory-recall-eval-gate.md:104`).
- A 2026-07-28 live run shows strong metrics (`evidence/3-14-eval-.../run_artifact.json:59-91`), but it is not signed off.
- **Impact:** The memory layer cannot be claimed launch-ready. A single good run artifact does not replace a ratified, reproducible baseline.

### Red Flag 7: Messaging table is violated in public-facing assets
- The brief’s table (`brief.md:251-268`) says: do not say “open source” for the whole product; do not say “NotebookLM alternative”; do not mention ChainLens.
- Current public copy violates all three:
  - `README.md:1,25`, `hero-section.tsx:658`, `docs/index.mdx:10`, `seo/json-ld.tsx:22-79` call the product “open-source research memory.”
  - `pricing-section.tsx:183`, `app/(home)/free/page.tsx:142,147`, `changelog/content/2026-07-05.mdx:13,17` call it “open source.”
  - `free/page.tsx:142,147` calls it a “ChatGPT alternative.”
  - `social-proof.tsx:35-83` and `changelog/2026-07-05.mdx:13` call it a “NotebookLM alternative.”
- **Impact:** This will trigger license/attribution backlash, confuse positioning, and invite competitor comparisons. It is a launch blocker.

> **Callout tiếng Việt:** *Public messaging đang vi phạm bảng NÓI/KHÔNG NÓI ở nhiều nơi: README, landing, pricing, changelog, social proof. Cần audit toàn bộ trước khi ra mắt.*

---

## 6. Optional Enhancements

- **Add a legal readiness milestone to the roadmap.** Make it the first gate in Phase 1, with a checklist (counsel opinion, `NOTICE`, attribution, license wording) and a go/no-go decision.
- **Build a competitive fast-follow teardown.** Document how NotebookLM, Perplexity, Mem0, and Exa could each copy the wedge in 6–12 months, and the counter-positioning for each.
- **Create an open-source attribution page.** Proactively disclose the SurfSense fork, the Apache-2.0/BSL split, and the ChainLens boundary. This turns a defensive legal risk into a trust signal.
- **Add a “Cloud-only features” tier in Phase 1.** Team collaboration, managed connectors, and compliance/retention should not wait for enterprise.
- **Publish a HN launch readiness checklist.** Convert the findings in this review into an owner-assigned, evidence-based go/no-go document.

---

*End of review.*
