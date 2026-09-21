---
title: 'technical research: jev-ultrafast browser agent → Nowing'
type: 'technical'
topic: 'browser-use/jev-ultrafast — integration fit for Nowing'
decision: 'Should Nowing integrate jev-ultrafast (or port its pattern) into the stack, and where'
source: 'native run (deepen of technical-typesafe-ai-jev-integration-2026-09-21)'
status: complete
preset: 'standard'
validation: 'normal'
created: '2026-09-21'
updated: '2026-09-21'
verified_claims: 5
unverified_claims: 1
---

# Technical research: jev-ultrafast browser agent → Nowing

**Decision this research serves:** Nowing có nên tích hợp `browser-use/jev-ultrafast` (hoặc port pattern của nó) vào stack, và nếu có thì ở đâu?

---

## Executive summary

**Verdict: KHÔNG tích hợp `jev-ultrafast` như một dependency — nhưng NÊN port 4 pattern cụ thể của nó vào Nowing, và dùng nó làm reference implementation cho Epic 39.**

Ba findings drive kết luận này:

1. **`jev-ultrafast` là một browser agent demo, không phải thư viện tích hợp được.** Nó attach vào Chrome profile thật của user qua `browser-harness` daemon (CDP, remote debugging) — không headless, không server-side, không embeddable. Nó là một **local desktop tool / marketing demo** cho Browser Use Cloud, với 3 commits bởi 1 người, ~50 PR cộng đồng chưa merge, và flagship demo đã hỏng sau 4 ngày. [3][6][8]

2. **Nhưng kiến trúc "Jev làm decision layer trong agent loop" của nó là reference implementation đầu tiên** cho đúng thứ Nowing đang build trong Epic 39 (DecisionService port). Cơ chế *speculative fan-out* — một request Jev chứa `operation` Choice + nhiều `target` Choice heads, chỉ validate head trúng tuyển — là pattern mà Epic 39.3 (entity resolution) có thể port trực tiếp cho two-stage dedup. [2]

3. **Zero independent validation.** Không có một third-party benchmark nào so với browser-use classic / Playwright+LLM / Computer Use / Stagehand. Ba lần chạy độc lập duy nhất đều fail/slow/broken (wrong steps, 12–17s từ Japan vs 7.1s claim, demo hỏng vì hardcoded date). Vendor tự thừa nhận "3 pairs too few for statistical claim (p=0.25)". Con số 14.7K★ là launch-week spike phân phối qua X/YouTube, không phải adoption. [1][5][6]

**Biggest caveat:** `jev-ultrafast` phụ thuộc hoàn toàn vào TypeSafe Jev API (mọi `choose()` fail nếu thiếu key) và giả định một Chrome desktop session. Nó **không thay thế** kế hoạch browser-control extension (MV3) mà Nowing đã proposal ngày 2026-08-04 — nó chỉ là một cách *khác* để drive browser, bị giới hạn MVP (no shadow DOM/frames/uploads) và không shippable cho end users.

---

## Dimension 1: What jev-ultrafast actually is

### Architecture (verified in code)

Một browser agent với loop: **observe → choose → act → re-observe**. [agent.py]

```
page → snapshot.js (1 CDP evaluate)
     → element table [n] role name · value
     → model.py choose() ──► 1 POST /v1/systemone
                              ├─ operation Choice (CLICK/TYPE_TEXT/SELECT/SCROLL/WAIT/DONE/BLOCKED)
                              └─ target Choice heads (1 per op, speculative)
     → validate_choice (strict)
     → browser.py act() via CDP (code-owned node IDs, occlusion checks)
     ↓ (only if op=TYPE_TEXT)
     small LLM → JSON {text} → typed into field
```

**Jev decides *everything* except text content.** Nó chọn operation + element index; nó **không bao giờ** emit selector, coordinate, hay JavaScript. Model output chỉ là một index vào một element table mà code sở hữu. [model.py, browser.py]

### The two core mechanisms

**Speculative fan-out** — `choose()` gửi MỘT request chứa `operation` question cộng với một `*_target` question cho mỗi operation khả dụng (`click_target`, `type_text_target`, `select_target`). Tất cả trả lời trong cùng 1 round trip; chỉ target head khớp với operation được chọn mới được validate + execute. → 2 quyết định, 1 network round trip. [2][model.py choose()]

**Dynamic indexed action space** — `action_space()` gán 1 index cho mỗi DOM node (node hỗ trợ cả click+fill dùng chung 1 index); native SELECT nhận composite target `index:optionN`; scroll/wait thành "controls"; DONE/BLOCKED append như operations. Cap 250 candidates. [model.py action_space(), snapshot.js]

### Execution hardening

- `validate_choice()`: probabilities sum≈1±0.02, chosen=argmax, all finite ∈[0,1], keys match ids. Fail → "no action executed". [model.py]
- `browser.py`: node IDs code-owned (WeakMap), re-resolve geometry + check :disabled/aria-disabled/inert/visibility/occlusion(`elementFromPoint`) trước input; real CDP mouse/key events; mutations never retried. [browser.py]
- Freshness: semantic marker/pageKey/per-node guard comparison (không phải mutation counting); scoped context (nearest form/dialog/row ≤6000 chars) cố ý cho phép unrelated visible changes. [snapshot.js, browser.py]
- Text helper: small OpenAI-compatible LLM, chỉ khi TYPE_TEXT; output phải parse JSON đúng `{"text": str}` ≤2000 chars; cached chỉ khi entire helper input identical. [model.py field_text()]

---

## Dimension 2: Maturity & evidence

### Vitality

| Signal | Reality |
|---|---|
| Stars | 14,765★ / 913 forks — nhưng chỉ **41 watchers** |
| Commits | **3 total**, tất cả bởi `gregpr07` (Gregor Žunič, browser-use founder/CTO), last push 2026-09-18 |
| PRs/issues | ~50 community PRs (retry, i18n, iframe, tab tracking, CI) + ~8 issues — **phần lớn chưa merge** |
| Shape | Installable lib (`jev-ultrafast 0.1.0`, exports Agent/Browser) + offline pytest + measurement scripts — **demo/showcase với library pretensions** |
| Purpose | README top banner = "Browser Use Cloud waitlist is open" — **funnel cho commercial cloud product** |

### Performance claims (self-reported, boundaries disclosed)

- Headline: Google Flights Zürich→London trong **7,073ms** @ 1× — 17 Jev requests, 10 interactions + 1 WAIT, 2 text-helper calls, median Jev 178ms. [1]
- Matched: median 9.450s→7.092s (25%↓), protocol calls 1092→101, TypeSafe req 22→17. Vendor disclose: "3 pairs too few for strong statistical claim (p=0.25)". [1]
- Token cost: 90,558 TypeSafe input + 6,325 output tokens cho 1 task; text helper $0.00006272. [1]
- Boundaries: timing starts sau initial page observation; excludes browser setup/nav/post-verify. [1]

### Independent reproductions: NONE successful

- **#67** (yonikremer): transit task "how long by bus" → "goes wrong in many steps"; forked to OpenRouter + self-check/retry → improved but "cost me a lot for calls". Maintainer: "let me run evals". [5]
- **#85** (kuroudo-ai): 9 identical runs from Japan → **12–17s/task** (vs 7.1s claim), client-link latency; Singapore user same + broken proxy connections. Praised per-action validation, adopted row-number-target idea. [5]
- **#93** (ffffj-ai): bundled Flights demo **unsatisfiable** — hardcoded goal date 2026-09-20 now past, aria-hidden in date picker → "blocked · no supported next action". [5]
- **ABSENCE**: không có third-party benchmark nào vs browser-use classic, Playwright+LLM, Computer Use, OpenAI Operator, hay Stagehand. [5]

### Community reception: mixed-to-skeptical

- HN: single thread 2026-09-17, **91 pts / 14 comments** — không front page (low cho repo 14.7K★; traffic đến từ X/YouTube). [6]
- "Timing starts after initial page observation — isn't this the part that takes most time?" (methodology challenge). [6]
- "It seems almost like a smart switch statement" / "at best misleading, this one also happens to be broken". [6]
- "You do not do all this with google flights. The link can be constructed with protobuf" (demo task trivially scriptable). [6]
- "I don't like paying AI tax to gate keepers" (cloud-model objection). [6]
- Independent clone wave: `vinnylarouge/jevlike` (1,155★), "Mini-Jev", "Sub-15ms local alternative", "Kev on Qwen3.5" — community building local substitutes rather than adopting paid API. [6][9]

---

## Dimension 3: Extractable patterns (the real value for Nowing)

Đây là những mechanism **reusable độc lập với browser** — mỗi cái cite file nguồn:

| # | Pattern | Mechanism | File |
|---|---|---|---|
| P1 | Dynamic indexed action space | 1 node = 1 index (multi-op shared); per-op target maps; composite `element:option`; ≤250 cap | model.py `action_space()` |
| P2 | **Speculative fan-out** | operation + all target heads trong 1 request; chỉ validate head trúng; unused heads never execute | model.py `choose()` |
| P3 | One-request-per-cycle | op + target share observed state; target premise names assumed op | model.py, design.md |
| P4 | **Strict validation-gated execution** | argmax + distribution-sum + finite + key-match; fail → no action | model.py `validate_choice()` |
| P5 | DONE ≠ verified | model DONE chỉ accept nếu page fresh(); outcome verify độc lập | agent.py, design.md |
| P6 | **Semantic freshness guard** | marker/pageKey/per-node guard compare (không mutation count); scoped context cho phép unrelated changes | snapshot.js, browser.py `fresh()` |
| P7 | Text-helper handoff | small LLM chỉ khi cần; JSON `{text}` ≤2000 validated; cache chỉ khi input identical | model.py `field_text()` |
| P8 | Consume-once + loop guards | decision null trước mutation (no double-click); logged trước post-action observe; 3 no-change → blocked | agent.py |
| P9 | Model output never = selectors/JS | node IDs code-owned WeakMap; executor recheck visibility/enabled/readonly/occlusion | browser.py |
| P10 | Performance posture | no screenshots default; 1 browser call/snapshot; 2rAF/50ms waits (200ms combobox) | browser.py `observe()` |

---

## Dimension 4: Fit with Nowing stack

### What Nowing already has (Epic 39 covers)

- **Confidence-gated execution** — `jev_router.py` gates hints ≥0.6; AD-J4 `ConfidenceGate`. jev-ultrafast's stricter `validate_choice` (argmax+sum) là refinement đáng port vào `DecisionService` (story 39.1).
- **One-request multi-question** — Epic 39 đã có "3 Nouls in one call" cho guardrails (INTEGRATION-POINTS TIER 1 #2). Speculative-head twist là refinement, không phải gap.
- **Question registry** — AD-J5 `QuestionRegistry` ↔ jev-ultrafast `questions.py` named constants. jev-ultrafast là concrete reference implementation tốt cho 39.1.
- **Model pinning + telemetry** — AD-J3/AD-J7 đã planned; jev-ultrafast logs model/usage/latency_ms per decision — cùng shape.
- **DONE ≠ verified** — Nowing's Jev decisions là advisory (routing hints, filters), không phải actuator loops → chưa cần; relevant nếu sau này build actuation.

### NEW patterns đáng port vào Nowing

1. **Speculative fan-out + per-head candidate narrowing** → **entity resolution (story 39.3)**. jev-ultrafast's target heads chỉ chứa compatible candidates, unused heads không validate. Nowing's two-stage dedup (heuristic narrow → Jev confirm) map trực tiếp: một request với `match_target` head chứa chỉ heuristic-passing candidates → `SpatialWindowedDeduplicator` (`app/services/dedup/spatial_windowed_dedup.py`), `bds_aggregator/dedupe.py`.

2. **Strict answer-schema validation** → **AD-J1 `DecisionResult` validation (`app/services/decision/service.py`, story 39.1)**. `validate_choice` (argmax + distribution-sum) chặt hơn threshold-only check hiện tại trong `jev_router.py`. Rẻ để port, ngăn acting trên malformed/miscalibrated answers.

3. **Consume-once decision semantics** → bất kỳ actuation path tương lai (sequencer condition firing `app/services/sequencer/service.py`, anti-bot triage). Null decision trước execute để retry không double-fire.

4. **Semantic freshness guard** → `app/services/anti_bot_escalation.py` + scraper re-visit logic — so sánh semantic state (URL + content hash + field values) thay vì raw HTML diff để quyết "observation còn valid không".

### Usable as a browser-automation dependency?

**KHÔNG — không dùng như dependency.**

- Nó là MVP demo (~840 LOC core), "two websites do not establish broad reliability" (chính README nói). [3]
- Hardcoded `api.typesafe.ai/v1/systemone` + `jev-latest`; Nowing pin `jev-1.13.0`. [4]
- Bound tới `browser-harness` daemon attach vào **user's existing Chrome profile** — giả định local desktop, không headless, không server-side. [4][7]
- No shadow-DOM/frames/uploads/popups/nested-scroll. [4]

**vs browser-control proposal (2026-08-04):** proposal đó chọn **Chrome MV3 extension trong logged-in session của chính user** (Manus "My Browser" model) vì lý do legal — user IP, user session, no server-side scrape. jev-ultrafast's model (owned background tab trong Chrome profile của user, focus emulation) là *architecturally adjacent* — cả hai đều tránh datacenter IP — nhưng là **local desktop tool**, không phải shippable extension; không thay thế extension plan.

**Tuy nhiên, 3 mechanism transfer trực tiếp vào content-script design của extension:**
- **Indexed element-table snapshot** — numbered accessible controls, thay raw DOM scraping — rẻ hơn Playwright MCP accessibility tree (theo proposal §9).
- **Semantic freshness marker** — cho Deal-Radar re-checks.
- **Operation+target single-request decision shape** — chạy trên Nowing `DecisionService` thay vì raw `typesafe.ai`.

---

## Cross-dimension insights

1. **jev-ultrafast là proof-of-concept cho đúng kiến trúc Nowing đang build** — nhưng chứng minh ở một domain khác (browser), không phải domain của Nowing (scraper/chat). Giá trị lớn nhất của nó cho Nowing là **validate rằng "Jev làm decision layer trong agent loop" là một pattern thật, có code đọc được** — Epic 39.1 có thể mượn `choose()`/`validate_choice()`/`questions.py` làm reference khi viết `DecisionService`.

2. **Khoảng cách hype-vs-reality là cảnh báo cho chính Nowing.** jev-ultrafast có 14.7K★, demo video 7s ấn tượng — và 0 independent reproduction, demo hỏng sau 4 ngày, 3 commits 1 người. Đây là launch-week artifact phục vụ funnel cho Browser Use Cloud. Bài học cho Nowing: đừng để Epic 39 dựa vào vendor benchmark; Vietnamese eval riêng (đã có, 96.3%) là đúng hướng.

3. **Strategic tension trong chính browser-use:** CTO của họ publish "The Bitter Lesson of Browser Agents" 2 ngày trước launch, argue rằng field nên abandon predefined action spaces và để models tự viết observations/actions qua raw CDP. `jev-ultrafast` là cực đối lập (indexed element table cứng, 8 ops). Repo này là *specialized fast demo*, không phải hướng đi chiến lược của công ty — điều đó hạ giá trị "đây là future của browser agents". [6]

4. **Pattern portability cao hơn code portability.** Phần giá trị (speculative fan-out, validation-gated execution, freshness guards, text-helper handoff) đều là *design patterns* đọc được trong ~200 LOC, không phải code Nowing nên vendor. Port vào `DecisionService` + extension content-script, giữ MIT attribution.

---

## Contrary evidence

- **"Smart switch statement" critique (HN):** một số người reduce "Jev picks operation+element" thành trivial branching. Phản biện công bằng: giá trị không nằm ở độ phức tạp của decision mà ở **calibrated confidence + typed output + 178ms latency** — nhưng critique đúng ở chỗ nó chưa chứng minh generalize ra ngoài demo tasks.
- **Methodology challenge (HN):** "timing starts after initial page observation" — phần tốn thời gian nhất (page load + first snapshot) nằm ngoài clock → con số 7.1s lạc quan hơn thực tế end-to-end.
- **Demo task trivially scriptable:** Google Flights có thể construct URL bằng protobuf không cần agent — demo chọn một task mà agent không cần thiết, làm yếu claim "generalizes".
- **CTO's own thesis opposes it:** browser-use's "Bitter Lesson" blog argue cho raw CDP / model-authored actions — nếu công ty tin điều đó, `jev-ultrafast` là dead-end showcase, không phải roadmap.
- **Independent clone beats it on scope:** `vinnylarouge/jevlike` và làn sóng local Jev clones cho thấy community muốn local/open hơn là paid cloud API — `jev-ultrafast` bị kẹt giữa "demo cho cloud" và "không phải production tool".

---

## Recommendations

### Cho Nowing integration

**R1: KHÔNG vendor `jev-ultrafast` như dependency. Dùng nó làm pattern reference cho Epic 39.**
- Confidence basis: high — nó là MVP demo Chrome-bound, không server-embeddable, không được maintain như library.
- Downstream: `ARCHITECTURE-SPINE.md` (jev-decision-service) — cite `model.py choose()` + `validate_choice()` làm reference implementation.

**R2: Port `validate_choice()` semantics vào `DecisionService` (story 39.1).**
- Hiện tại `jev_router.py` chỉ check `confidence >= threshold`. Port thêm: probabilities sum≈1, chosen=argmax, keys match criteria ids, all finite ∈[0,1]. Fail → discard answer, không act.
- Confidence basis: high — rẻ (thêm ~15 LOC validation), chặn malformed/miscalibrated answers trước khi gate.

**R3: Port speculative fan-out + per-head narrowing vào entity resolution (story 39.3).**
- Two-stage: heuristic (Jaccard/spatial window) narrow candidates → một Jev request với `match_decision` Choice + `match_target` head chứa chỉ heuristic-passing candidates. Cùng shape với jev-ultrafast's op+target.
- Confidence basis: high — map trực tiếp lên `SpatialWindowedDeduplicator` + `bds_aggregator/dedupe.py`; cookbook entity-alignment cũng validate.

**R4: Khi build browser-control extension (theo proposal 2026-08-04), mượn 3 mechanism — không phải code.**
- Indexed element-table snapshot (numbered accessible controls) thay raw DOM scrape trong content-script.
- Semantic freshness marker (pageKey + per-node guard) cho Deal-Radar re-checks.
- Operation+target single-request decision shape chạy trên `DecisionService`.
- Confidence basis: medium — extension plan chưa build; jev-ultrafast chứng minh mechanism works nhưng trong context desktop-CDP, cần adapt cho MV3 content-script.

**R5: Consume-once decision semantics làm invariant cho bất kỳ actuation path nào.**
- Null decision trước execute → retry không double-fire. Áp dụng khi Jev gate side-effecting actions (sequencer conditions, anti-bot escalation) — không cần cho Epic 39 advisory hints.
- Confidence basis: high — cheap invariant, prevents a real bug class.

### NOT recommended

- **Đừng vendor/fork repo** — 3 commits 1 người, ~50 PR unmerged, flagship demo đã hỏng, Chrome-profile-bound, README là Cloud waitlist funnel.
- **Đừng kỳ vọng nó thay browser-control extension plan** — nó là desktop tool, không shippable cho end users, không giải quyết legal model (nó vẫn là user's own browser, nhưng không phải extension).
- **Đừng tin con số 7.1s / 25% như evidence generalizes** — vendor tự nói p=0.25, 3 pairs, 1 task, 1 profile; zero independent reproduction.

---

## Open questions

1. **TypeSafe "speculative fan-out" pattern doc** (`docs.typesafe.ai/patterns/fan-out`) — mechanism đã rõ trong code nhưng official guidance chưa đọc; có thể chứa recommended patterns cho Nowing.
2. **Browser Use Cloud** — `jev-ultrafast` là funnel cho nó; nếu Nowing cần hosted browser-agent capability sau này, Cloud waitlist có thể là option — nhưng chưa có pricing/SLA.
3. **`docs/full-speed-measurement.json` / `flights-measurement.json`** — per-run token counts + source hashes committed; chưa đọc (budget) nhưng available để audit cost claims.
4. **Unmerged PRs** (iframe, tab tracking, injectable providers, CI) — signal roadmap; nếu community fork consolidates, một fork maintained hơn có thể xuất hiện.
5. **Semantic freshness guard cho scraper** — pattern port được về mặt concept nhưng Nowing's scrapers không observe DOM theo cùng cách (chúng fetch + parse); mức độ áp dụng cần prototype.

---

## Source appendix

| # | Claim/finding | Publisher | Pub date | Accessed | Confidence |
|---|---|---|---|---|---|
| 1 | Perf: 7.073s Flights, 9.450→7.092s matched, 1092→101 protocol calls, 17 Jev req, 90,558 input tokens, p=0.25 disclosed | [browser-use/jev-ultrafast docs/performance.md](https://github.com/browser-use/jev-ultrafast/blob/main/docs/performance.md) | 2026-09-17 | 2026-09-21 | High (self-reported, boundaries disclosed) |
| 2 | Speculative fan-out in code: 1 request = operation + per-op target heads | [model.py](https://github.com/browser-use/jev-ultrafast/blob/main/jev_ultrafast/model.py) | 2026-09-17 | 2026-09-21 | High |
| 3 | Repo vitality: 3 commits, 1 author (gregpr07), ~50 unmerged PRs, Cloud waitlist funnel | [GitHub API + README](https://github.com/browser-use/jev-ultrafast) | 2026-09-21 | 2026-09-21 | High |
| 4 | Hard deps: browser-harness==0.1.13 (real Chrome CDP), TYPESAFE_API_KEY, TEXT_MODEL_API_KEY; MVP limits | [pyproject.toml, browser.py, README](https://github.com/browser-use/jev-ultrafast) | 2026-09-17 | 2026-09-21 | High |
| 5 | Zero independent reproductions: #67 wrong steps, #85 Japan 12-17s, #93 demo broken | [GitHub issues](https://github.com/browser-use/jev-ultrafast/issues) | 2026-09-20→21 | 2026-09-21 | High |
| 6 | HN reception 91pts/14c skeptical; CTO 'Bitter Lesson' argues opposite; clone wave | [HN Algolia](https://news.ycombinator.com/item?id=49735979), [browser-use blog](https://browser-use.com/posts/bitter-lesson-browser-agents) | 2026-09-15/17 | 2026-09-21 | High |
| 7 | browser-harness: MIT, ~17.9k★, PyPI 0.1.13, 'control your real browser' CDP daemon | [PyPI + GitHub](https://pypi.org/project/browser-harness/) | 2026-09 | 2026-09-21 | High |
| 8 | Design rationale + boundaries (2 websites ≠ reliability, DONE≠verified, scoped guards) | [docs/design.md](https://github.com/browser-use/jev-ultrafast/blob/main/docs/design.md) | 2026-09-17 | 2026-09-21 | High |
| 9 | jevlike independent clone (1,155★) + local-clone wave (Mini-Jev, Kev, sub-15ms) | [GitHub vinnylarouge/jevlike + HN](https://github.com/vinnylarouge/jevlike) | 2026-09-16→21 | 2026-09-21 | Medium |

---

## Staleness map

| Claim | Class | Pub date | Freshness bar | Re-check by |
|---|---|---|---|---|
| Repo vitality (3 commits, unmerged PRs) | ecosystem | 2026-09 | ≤1 mo | 2026-10-21 |
| Issue tracker state (#67/#85/#93) | risk | 2026-09 | ≤1 mo | 2026-10-21 |
| browser-harness 0.1.13 pin | version | 2026-09 | ≤1 mo | 2026-10-21 |
| Perf 7.073s / 25% / protocol calls | performance | 2026-09 | ≤3 mo (AI-adjacent) | 2026-12-21 |
| Browser Use Cloud waitlist | ecosystem | 2026-09 | ≤3 mo | 2026-12-21 |
| Local-clone wave (jevlike etc.) | ecosystem | 2026-09 | ≤3 mo | 2026-12-21 |
| jev-ultrafast as dependency (verdict) | recommendation | 2026-09 | ≤6 mo | 2027-03-21 |

**Earliest re-check:** 2026-10-21 — theo dõi xem ~50 community PRs có được merge không (test của "sustained project vs launch spike"), và browser-harness version drift.

---

## Parent-run cross-link

Đây là **deepen** của `technical-typesafe-ai-jev-integration-2026-09-21` (Jev decision-layer verdict: integrate Jev as decision primitive layer; Epic 39 created). Findings ở đây **củng cố** verdict đó — Jev-as-decision-layer là pattern thật được browser-use dùng production-shaped — đồng thời **siết lại**: giá trị nằm ở porting patterns vào Nowing's own `DecisionService` + extension content-script, không phải adopting external browser-agent dependencies.
