# Brief — jev-ultrafast browser agent → Nowing integration

**Decision:** Nowing có nên tích hợp `browser-use/jev-ultrafast` (hoặc port pattern của nó) vào stack, và nếu có thì ở đâu?

**What the target is (primary crawl, 2026-09-21):**
- Browser Use × TypeSafe collaboration: browser agent where **Jev picks operation + element**, small LLM only writes text when op=TYPE_TEXT
- Dynamic indexed action space: every observation → element table `[n] role name · value`; ops = CLICK/TYPE_TEXT/SELECT/SCROLL_UP/SCROLL_DOWN/WAIT/DONE/BLOCKED
- **Speculative fan-out**: operation + target heads share ONE TypeSafe request (2 decisions, 1 round trip)
- Perf claims: Google Flights Zürich→London in 7.073s; median 9.450s→7.092s (25%↓); browser protocol calls 1092→101. Wikipedia task 2.798s, hotel task 1.896s
- Limits: MVP — no shadow roots/frames/canvas/uploads/popups/nested-scroll/arbitrary-keyboard; "3/3 runs" not a reliability benchmark; needs browser-harness + Chrome remote debugging
- 14,759★ / 912 forks, created 2026-09-16, MIT license, Python
- Files: agent.py (loop), snapshot.js (DOM→indexed controls), browser.py (connection/exec), model.py (dynamic op/target heads), questions.py (model instructions), demo.py (inspector)

**Nowing stack context (for fit reasoning, NOT evidence):**
- Jev already committed: `JevRouterMiddleware` wired (flag OFF), Epic 39 (DecisionService port, QuestionRegistry, 8 stories), Vietnamese eval 96.3%/308ms
- Scraper modules (batdongsan, chotot, muaban, facebook groups, telegram, linkedin, muasamcong, topcv/itviec/vietnamworks)
- `browser-control-integration-proposal-2026-08-04.md` exists in planning-artifacts
- Voice agent (LiveKit + Silero VAD), LangGraph multi-agent chat, ChainLens research
- Epic 39.1 builds DecisionService port — jev-ultrafast's model.py/questions.py is the first production-shaped reference for "Jev as decision layer in agent loop"

**Research questions per dimension:** see plan gate (5 dims: what-is / maturity / pattern-extractability / nowing-fit / risk).

**Parent run:** `technical-typesafe-ai-jev-integration-2026-09-21` (Jev decision-layer verdict + Epic 39). This is a DEEPEN — one entity drilled, parent untouched except cross-links.

**Run folder:** `_bmad-output/planning-artifacts/research/technical-jev-ultrafast-browser-agent-integration-2026-09-21/`
