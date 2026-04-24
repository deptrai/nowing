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
