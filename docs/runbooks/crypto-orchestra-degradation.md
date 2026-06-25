# Runbook: Crypto Orchestra — Graceful Degradation Alert

**Audience:** On-call engineers  
**Alert name:** `crypto_orchestra_degradation_rate_low`  
**SLO target:** Degradation rate ≥ 98% (success + partial responses / total requests)

> **Note (2026-04-24):** The 98% SLO is derived from spec NFR-Q3, but the offline
> 100-query benchmark (`TestDegradationRateBenchmark`) is currently opt-in via
> `@pytest.mark.slow` + `ANTHROPIC_API_KEY`. It runs **advisory only** — not in
> normal CI. Until a nightly LLM-budgeted pipeline is in place, treat production
> alert signal as the authoritative gate, not the benchmark test.

---

## 1. Alert triggered when

P95 graceful degradation rate drops below 98% over a rolling 1-hour window.

**Prometheus query (degradation rate):**

```promql
(
  sum(rate(crypto_orchestra_graceful_degradation_total{outcome=~"success|partial"}[1h]))
  /
  sum(rate(crypto_orchestra_graceful_degradation_total[1h]))
) < 0.98
```

**Dashboard panel:** "Crypto Orchestra → Degradation Rate" gauge (must show ≥ 98%).

---

## 2. Diagnose

### Step A — Identify which agent has elevated error rate

```promql
# Top error sources by agent + type in last 1h
topk(10, sum by (agent_name, error_type) (
  rate(crypto_orchestra_agent_errors_total[1h])
))
```

Common patterns:
- `agent_name="defillama_analyst", error_type="server_error"` → DeFiLlama API outage
- `agent_name="news_analyst", error_type="rate_limit"` → CryptoPanic quota exhausted
- `agent_name="smart_contract_analyst", error_type="timeout"` → GoPlus Labs latency spike
- `agent_name="sentiment_analyst", error_type="network_error"` → general network issue

### Step B — Check external API status pages

| Service | Status URL |
|---------|-----------|
| DeFiLlama | https://status.defillama.com/ |
| CoinGecko | https://status.coingecko.com/ |
| GoPlus Labs | https://gopluslabs.io/ (no official status page — monitor response times) |
| CryptoPanic | https://cryptopanic.com/ (check manually) |

### Step C — Check recent deploys

```bash
git log --oneline -20
```

Look for changes to:
- `app/agents/new_chat/tools/` — tool error handling
- `app/agents/new_chat/subagents/` — sub-agent specs
- `app/agents/new_chat/chat_deepagent.py` — orchestration logic

### Step D — Check rate-limit degradation tier (added Story 0.6b)

```bash
# Look for tier-transition log markers (last 10 min):
tail -n 5000 /var/log/nowing/backend.log | grep -E "rate_limit_degraded|rate_limit_paced|synthesis_paced_retry" | tail -20
```

**Interpretation:**

| Log pattern | Tier | Expected behavior |
|-------------|------|-------------------|
| `parallel_spawn: 6 agents dispatched` | Tier 1 | Normal. Full-analysis in <30s. |
| `rate_limit_degraded (Tier 2): spawning sequentially (next=X, N/6 remaining)` | Tier 2 | 1 agent per LangGraph turn. Expect ~15-25s total. |
| `rate_limit_paced (Tier 3): sleeping 7.0s before spawning X` | Tier 3 | Each agent emission blocked 7s. Total ~45-50s is **EXPECTED**, not an incident. |
| `rate_limit_reduced_scope (Tier 3): capping analysis to 2/6 agents` | Tier 3 | Analysis scope reduced to top-2 deterministic-API agents under sustained pressure. User receives partial answer (~30s) instead of error. **EXPECTED** on strict-RPM providers. |
| `synthesis_paced_retry (Tier 3): attempt N/3 hit 429, sleeping 7.0s` | Tier 3 | Main synthesis retry. Up to 3 attempts — if all fail, stream errors out. |
| `provider_rate_gate: spacing X.Ys before next call (min_interval=Y.Ys, elapsed=Z.Zs)` | Gate | Min-interval pacer enforcing serialization between LLM calls. Normal operation — prevents any possibility of burst to provider. |

**Latency spike caveat**: If monitoring flags a P95 latency spike for crypto queries but log shows Tier 3 active, this is the **degradation ladder working as designed** — system chose slow-completion over fail-fast. Confirm with `GRACEFUL_DEGRADATION_COUNTER{outcome="rate_limit_paced"}` rate. Only escalate as an incident if:
- Tier 3 is active for > 15 minutes (likely provider quota truly exhausted, not transient)
- Synthesis retries hit 3/3 failure → users see error despite ladder

### Step E — Check sub-agent resilience + partial salvage

```bash
tail -n 5000 /var/log/nowing/backend.log | grep -E "subagent_retry|subagent_exhausted|yielding partial" | tail -20
```

**Interpretation:**

| Log pattern | Layer | Meaning |
|-------------|-------|---------|
| `subagent_retry: <name> attempt N/3 hit rate_limit, sleeping Xs` | 4a | Sub-agent auto-retrying on 429. Paced backoffs 5s → 15s → 45s. **EXPECTED** under pressure — not an incident. |
| `subagent_exhausted: <name> gave up after 3 retries — returning error ToolMessage` | 4a | Sub-agent terminal failure. Stream continues; main agent synthesizes with remaining agents. **Not** a stream crash. |
| `[stream_new_chat] yielding partial analysis: N completed, M errored` | 4b | Synthesis step itself exhausted — last-resort salvage fired. User sees partial results message instead of generic error. |

**Latency caveat**: a single sub-agent retry chain can consume ≤65s (5+15+45). With 6 agents retrying concurrently, worst-case query latency ~4-5 minutes. Monitoring should tag crypto queries separately to avoid polluting global P95.

**Incident ONLY if**:
- `subagent_exhausted` rate > 10% over 15 minutes (provider quota truly over budget — need upgrade)
- `yielding partial analysis: 0 completed, 6 errored` appears frequently (gate mis-tuned or provider throttled our entire IP)
- Users report never seeing "⚠️ Phân tích bị giới hạn…" → partial salvage broken (check `_extract_partial_analysis` import + checkpointer availability)

---

**Tunables** (set via env + restart, don't hot-patch):
```
# Reactive 3-tier ladder
CRYPTO_ORCHESTRA_RATE_LIMIT_COOLDOWN=60      # cooldown window (seconds)
CRYPTO_ORCHESTRA_ESCALATION_THRESHOLD=3      # consecutive 429s → Tier 3
CRYPTO_ORCHESTRA_PACED_DELAY_SECONDS=7       # sleep between agents in Tier 3

# Proactive global rate gate (optional — set per provider tier)
PROVIDER_RPM_LIMIT=0                         # 0 = disabled. Set to 10 (TrollLLM) / 50 (Anthropic Tier 1) / 1000 (Tier 2). Derives min_interval = WINDOW/LIMIT
PROVIDER_RATE_WINDOW_SECONDS=60              # rolling window
PROVIDER_RATE_MAX_WAIT_SECONDS=90            # max wait per call (safety ceiling)

# Unbounded sub-agent retry (safety net for gate drift)
SUBAGENT_RETRY_MAX_WALL_SECONDS=900          # 15 min absolute cap per sub-agent
SUBAGENT_RETRY_BASE_BACKOFF=5                # first retry delay (doubles each attempt)
SUBAGENT_RETRY_MAX_BACKOFF=120               # cap for exponential backoff
```

---

## 3. Mitigate

### Scenario A: External API is down (DeFiLlama, GoPlus, etc.)

**Expected behavior:** Agent should already be degrading gracefully (returning partial analysis with transparency note). No immediate action needed unless degradation rate drops below 95%.

**If degradation rate drops below 95%:**
1. Verify the affected agent's tool code returns `{"error": "..."}` on API failures (not raising exceptions)
2. Check tool timeout settings — reduce if external API is consistently slow:
   ```python
   # app/agents/new_chat/tools/defillama.py
   _TIMEOUT = 15.0  # reduce from 30.0 if needed
   ```
3. Consider disabling the affected agent via feature flag (see step C)

### Scenario B: Tool code bug introduced by recent deploy

1. Identify commit that changed the affected tool
2. **Option 1 — Rollback:** `git revert <commit>` + deploy
3. **Option 2 — Hotfix:** patch the tool to catch the new exception and return `{"error": "..."}` 
4. Verify with test: `uv run pytest tests/integration/agents/test_graceful_degradation.py::TestToolLevelErrorHandling -v`

### Scenario C: Agent consistently crashing (not returning graceful error)

If a sub-agent is **raising exceptions** instead of returning `{"error": "..."}` — i.e., the graceful-degradation contract is broken — the mitigation path is **revert + redeploy**, not runtime toggling. There is no admin feature-flag endpoint for individual agents (removed from spec on 2026-04-24; a proper flag system requires a separate story).

1. Identify the commit that introduced the crash:
   ```bash
   # Bisect around the window where degradation rate started dropping
   git log --oneline --since="yesterday" -- nowing_backend/app/agents/new_chat/
   ```
2. Revert the offending commit and deploy:
   ```bash
   git revert <sha>
   git push origin main  # trigger CI/CD deploy pipeline
   ```
3. While the revert is deploying, if the incident is severe (>25% of requests failing):
   - **Page the team** — a runtime mitigation (hotfix PR that wraps the crashing tool in a try/except returning an error dict) is faster than a full revert.
   - Template hotfix:
     ```python
     # In app/agents/new_chat/tools/<affected_tool>.py
     try:
         ...existing code...
     except Exception as exc:
         logger.warning("<tool> error: %s", type(exc).__name__, exc_info=True)
         return {"error": f"Failed to fetch <resource>: {type(exc).__name__}"}
     ```

**Future improvement** (tracked separately): introduce a per-agent feature flag table so ops can disable `defillama_analyst`, `news_analyst`, etc. without a deploy. Not in scope for Story 0.6.

---

## 4. Escalate

Escalate to **senior engineer / team lead** if:
- Degradation rate persists below 95% for more than **4 hours**
- More than **2 agents** are simultaneously failing
- Catastrophic failures (all 4 agents) account for **> 10% of requests**
- The failure correlates with increased error rates in **other application services** (may indicate infrastructure issue)

**Escalation channel:** `#crypto-orchestra-incidents` Slack channel  
**PagerDuty:** `crypto-orchestra-critical` policy

---

## 5. Post-incident

After resolving:
1. Verify degradation rate returns to ≥ 98% on the dashboard
2. Run the fast integration test suite:
   ```bash
   cd nowing_backend
   uv run pytest -m integration tests/integration/agents/test_graceful_degradation.py::TestToolLevelErrorHandling -v
   ```
3. Add regression test if a new error mode was discovered
4. Update this runbook if a new external service or failure mode was encountered
