# DIGEST — dim1+2: what-is jev-ultrafast + maturity/evidence (R1)

Source: primary crawl of repo code/docs via raw.githubusercontent + api.github.com, accessed 2026-09-21.

## Architecture (verified in code)

- Loop: observe (1 JS DOM snapshot) → 1 TypeSafe `choose()` → execute via CDP → re-observe. `tick` = predict+act; `run()` yields per tick until DONE/BLOCKED. [agent.py]
- Jev decides ONLY operation + target. Never emits selectors/coordinates/code. Execution is code-owned: model output → observed element ID via JS WeakMap node cache. [model.py, browser.py]
- **Speculative fan-out**: `choose()` = ONE request with `operation` question + one `*_target` question per available op (click/type_text/select_target), all answered in single round trip; only the target head matching chosen op is validated/consumed. [model.py choose()]
- **Dynamic indexed action space**: `action_space()` = one index per DOM node (node supporting click+fill shares index, multiple ops); per-op target maps; native SELECT → composite targets `index:optionN`; scroll/wait → "controls"; DONE/BLOCKED appended as operations. Snapshot caps 250 action candidates. [model.py action_space(), snapshot.js]
- Text gen = separate small OpenAI-compatible LLM, only on TYPE_TEXT; output JSON `{text}` ≤2000 chars, never invented info; cached across stale retry only if entire helper input identical. [model.py field_text(), agent.py pending_text]
- Freshness: WeakMap node identity + pageKey + per-node guard (role/name/value/checked/href/nearby innerText ≤6000). `fresh()` compares marker/guards before act; StalePage → re-observe+re-predict. Fingerprint = sha256{url,text,actions,scroll}. [snapshot.js, browser.py]
- Execution hardening: before input JS re-resolves geometry, checks :disabled/aria-disabled/inert/visibility/occlusion(elementFromPoint); real CDP mouse events; fill = select-all + Input.insertText; mutations never retried; logged before post-action observe. [browser.py]
- Post-input waits: 2 rAF/50ms general; ARIA combobox fills wait ≤200ms for visible autocomplete (aria-controls/owns). [browser.py observe()]
- demo.py = loopback-only HTTP inspector (127.0.0.1:8766), token auth, Host/Origin checks — local UI, not in loop. [demo.py]

## Jev I/O contract

- Input state: `{page:{url,title,text≤6000 visible}, elements:[{index,label,role,value,checked,selected,expanded,operations,options?}], recent_actions:last10{action,kind,text,page_changed}}`. NO screenshot in default loop. [model.py choose()]
- Output: per-question `choice` + `probabilities` (sum≈1±0.02, chosen=argmax) + `confidence`∈[0,1]. Decision={choice(element/control id), operation(CLICK/TYPE_TEXT/SELECT/SCROLL_UP/SCROLL_DOWN/WAIT/DONE/BLOCKED), target, probabilities, usage, latency_ms}. Strict validate_choice rejects malformed → "no action executed". [model.py]
- No Noul in current code — design.md: old flat-choice/lookahead/Noul replaced by operation/target probability distributions. [docs/design.md]

## Performance (self-reported, boundaries disclosed)

- Headline 7,073ms Flights (Zürich→London one-way Sep20'26): 17 Jev req, 10 interactions + 1 WAIT, 2 text-helper calls, median Jev 178ms, Mercury 'Zurich' 581ms/'London' 346ms. [performance.md]
- Matched: 6 alternating runs (3 pairs) same task/profile/models → median 9.450s→7.092s (25%↓), protocol calls 1092→101, TypeSafe req 22→17. **Authors disclose: '3 pairs too few for strong statistical claim (two-sided sign-test p=0.25)'** — small controlled comparison, not benchmark. [performance.md]
- Boundaries: timing starts first prediction AFTER homepage observe; excludes browser setup/nav/post-verify; includes model/text/stale/loading. Baseline=frozen commit 68c077bf. Raw per-run JSON committed. [performance.md]
- Reproducibility: partial — measurement JSON + scripts in-repo, flights.py independently verifies; but depends on live Google/network/paid APIs. **Bundled Flights demo already broken (goal date 2026-09-20 past — open issue).**

## Hard limits (consistent across README/perf/design/code)

- No shadow roots, no frames (unmerged PR adds same-origin iframe), no canvas, no file uploads, no pop-up/new tabs (unmerged PR adds tab tracking), no nested scrolling, no arbitrary keyboard widgets; password/file/hidden excluded in snapshot.js safe(); no full accessible-name algorithm; max 250 action candidates; DONE never independent evidence. [README, performance.md, design.md, snapshot.js]
- In-code only: viewport hardcoded 1120×780; scroll delta fixed 560px @ fixed coords(550,650); visible text ≤6000 chars; field text ≤2000; MAX_STEPS=60 actions / 120 model calls per run. [browser.py, snapshot.js, questions.py, agent.py]

## Dependencies (each is a hard fail point)

- `browser-harness==0.1.13` (browser-use/browser-harness ~17.9k★): daemon `ensure_daemon` exposing CDP websocket to user's REAL Chrome. `cdp()` calls: Target.createTarget/attachToTarget, Runtime.evaluate, Input.*. Requires Chrome remote debugging enabled. Without: NO browser connection — agent can't start. [pyproject, browser.py]
- `TYPESAFE_API_KEY`: Bearer to api.typesafe.ai/v1/systemone, model `TYPESAFE_MODEL` default jev-latest (perf used jev-1.13.0). Without: every choose() fails — no decisions. [model.py]
- `TEXT_MODEL_API_KEY`: only for TYPE_TEXT. .env.example default OpenRouter inception/mercury-2.5 reasoning off; CODE default is DeepSeek api.deepseek.com/v1 deepseek-chat. Without: field_text raises — click/select/scroll tasks still work, any form-filling fails. No text hardcoded/guessed. [model.py, .env.example]
- Only other dep: httpx[http2]; Python ≥3.12; MIT; hatchling.

## Vitality / maturity

- Created 2026-09-16, last push 2026-09-18 — **3 commits total, ALL by one person (gregpr07 / Gregor Žunič, browser-use founder)**. 14,765★, 913 forks, 102 open issues+PRs, MIT, Python. [GitHub API]
- High community PR activity: ~45 open PRs 2026-09-19→21 (retry, i18n/UTF-8 Windows, iframe, tab tracking, injectable providers, CI) + ~8 issues incl real bugs (no-progress guard disabled by page_changed:null; invalid JSON leaks; Japan latency 12-17s). Maintainer merged few; last maintainer commit 2026-09-18. [GitHub issues]
- Shape: installable lib (pyproject, hatchling, `jev-ultrafast 0.1.0`, exports Agent/Browser, console `jev`→demo) + offline pytest + measurement scripts. **A demo/showcase with library pretensions, not a maintained multi-contributor library; README pushes Browser Use Cloud waitlist.**

## Cost per run

- Flights: 17 Jev req = 90,558 input + 6,325 output tokens (no $ disclosed for TypeSafe); text helper 2 OpenRouter calls = $0.00006272. Budget = 120 decisions / 60 actions per run. [performance.md, agent.py]

## Leads / NOT found

- Not read: docs/full-speed-measurement.json, flights-measurement.json; unmerged PRs (iframe/tab/providers); docs.typesafe.ai speculative fan-out pattern doc.
- NOT found: Noul in current code (legacy only); TypeSafe dollar cost/task; CI config on main; shadow-root/frame handling in snapshot.js (confirmed absent — light DOM only); multi-task reliability benchmark.
