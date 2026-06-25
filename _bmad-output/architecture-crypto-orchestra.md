# Kiến Trúc Crypto Orchestra

## Tổng Quan

Crypto Orchestra là hệ thống phân tích crypto đa-agent của Nowing. Khi user yêu cầu phân tích token, main agent spawn **7 sub-agents chuyên biệt** chạy song song, mỗi agent có scoped tool list riêng. Kết quả được tổng hợp thành structured report với inline citations.

```
User: "Phân tích toàn diện UNI"
         │
         ▼
┌─ Main Agent (LangGraph) ──────────────────────────────────┐
│  ParallelSpawnDirectiveMiddleware inject directive:        │
│  "Spawn 6-7 agents song song qua task() tool"             │
│                                                            │
│  task(tokenomics_analyst, "Analyze supply/vesting UNI")    │
│  task(defillama_analyst, "Analyze TVL/DeFi metrics UNI")   │
│  task(yield_optimizer, "Find best yields for UNI")         │
│  task(smart_contract_analyst, "Security check UNI")        │
│  task(news_analyst, "Latest news about UNI")               │
│  task(sentiment_analyst, "Market sentiment for UNI")       │
│  task(whale_tracker, "Smart money flows for UNI")  [flag]  │
│                                                            │
│  ← All results return as ToolMessages                      │
│  → Synthesis phase: compile report with [[cite:]] tags     │
└────────────────────────────────────────────────────────────┘
```

## Sub-Agent Specs

Mỗi sub-agent được định nghĩa bởi spec file tại `subagents/crypto/`, chứa:
- `NAME` — agent identifier (dùng trong `task(subagent_type=...)`)
- `DESCRIPTION` — khi nào dùng agent này
- `ALLOWED_TOOLS` — scoped tool list (NFR-CS4: tránh context confusion)
- `PROMPT` — system prompt < 500 tokens (NFR-CS1: tiết kiệm cost khi spawn nhiều agents)

### Agent Inventory

| Agent | Spec File | Tools | Chức năng |
|-------|-----------|-------|-----------|
| `tokenomics_analyst` | tokenomics_spec.py | coingecko_info, tokeninsight_rating, tokeninsight_research, live_token_data, live_token_price, chainlens_research | Supply schedule, vesting, distribution, inflation/deflation |
| `defillama_analyst` | defillama_spec.py | defillama_protocol, tvl_overview, yields, stablecoins, bridges, live_token_data, live_token_price, chainlens_research | TVL, DeFi metrics, protocol breakdown |
| `yield_optimizer` | yield_optimizer_spec.py | defillama_yields, defillama_protocol, check_token_security, live_token_data, chainlens_research | Yield recommendations theo risk tier, security gate |
| `smart_contract_analyst` | smart_contract_spec.py | contract_info, token_security, certik_audit_score, certik_incident_history, chainlens_research | Rug-pull detection, honeypot, tax analysis, audit scores |
| `news_analyst` | news_spec.py | crypto_news, coingecko_info, live_token_data, live_token_price, chainlens_research | Latest news, market developments, token fundamentals |
| `sentiment_analyst` | sentiment_spec.py | cmc_sentiment, reddit_sentiment, live_token_price, chainlens_research | Fear & Greed Index, Reddit sentiment, social signals |
| `whale_tracker` | whale_tracker_spec.py | nansen_smart_money, nansen_wallet_label, nansen_token_god_mode, run_dune_query, live_token_data, chainlens_research | Smart money flows, top holders, accumulation signals |

### Spawn Ordering (Priority)

`ParallelSpawnDirectiveMiddleware._COMPREHENSIVE_AGENTS` xác định thứ tự:

1. **Easy-Wins Tier** (deterministic APIs, thấp risk rate-limit):
   - `tokenomics_analyst` — CoinGecko + TokenInsight
   - `defillama_analyst` — DeFiLlama (unlimited)
   - `yield_optimizer` — DeFiLlama yields + security check
2. **Chainlens-heavy Tier**:
   - `smart_contract_analyst` — Etherscan + GoPlus + CertiK
   - `news_analyst` — CryptoPanic + CoinGecko
   - `sentiment_analyst` — CMC + Reddit
3. **Feature-flagged**:
   - `whale_tracker` — Nansen-heavy, appended khi `WHALE_TRACKER_ENABLED=true`

Trong điều kiện bình thường, tất cả agents spawn song song trong 1 model step. Dưới rate-limit pressure, spawned tuần tự theo thứ tự priority.

## Middleware Stack (Crypto-specific)

### ParallelSpawnDirectiveMiddleware
- **Detect**: Nhận diện crypto analysis request từ user message (keyword matching: "phân tích", "analysis", "evaluate", "comprehensive review", etc.)
- **Inject**: Append directive vào system prompt hướng dẫn main agent spawn tất cả agents song song
- **Synthesis**: Sau khi tất cả sub-agents trả về, inject synthesis directive: "Compile report NOW using existing ToolMessages"
- **Citation guidance**: Hướng dẫn dùng `[[cite:id]]value[[/cite]]` syntax cho mỗi data point

### SubAgentResilienceMiddleware (Sub-agent only)
- Retry with exponential backoff cho rate-limit errors
- Max attempts: `SUBAGENT_RETRY_MAX_ATTEMPTS` (default 5)
- Max backoff: `SUBAGENT_RETRY_MAX_BACKOFF` (default 120s)
- Non-rate-limit exceptions bubble up immediately

### SourceAttributionMiddleware
- Track mỗi tool call: source domain, fetched timestamp, raw result
- Emit `orchestra-spawn`, `data-orchestra-source-fetched`, `data-orchestra-model-attribution` events
- Events persist to `chat_run_events` table cho replay

### _build_gp_middleware() — Per-Agent Factory
- NFR-CS4: mỗi sub-agent nhận **fresh middleware instances** (không share state)
- Middleware stack giống main agent nhưng KHÔNG có ParallelSpawnDirective (sub-agents không spawn sub-sub-agents)

## Narration Templates (`narration_templates.py`)

Deterministic string templates (không dùng LLM) cho orchestra events:

### Pre-call Narration
Emit TRƯỚC tool execution, hiển thị trên FE dạng status update:
```
"Đang query CoinGecko cho thông tin token..."
"Đang kiểm tra bảo mật hợp đồng thông minh qua GoPlus..."
"Đang phân tích dòng tiền smart money từ Nansen..."
```

### Post-call Narration
Emit SAU tool execution, tóm tắt 1-2 key findings:
```
"Thấy TVL $3.2B, tăng 2.1% vs 7d"
"CertiK score 85/100"
"TokenInsight A rating"
```

### Source Domain Mapping
`TOOL_SOURCE_MAP` maps tool_name → `(domain, favicon_url, deeplink_template)`:
- `get_coingecko_token_info` → `coingecko.com`
- `get_defillama_protocol` → `defillama.com`
- `get_certik_audit_score` → `certik.com`
- `get_nansen_smart_money` → `nansen.ai`
- etc.

Dùng cho FE citation chips: hiển thị favicon + domain label + clickable deeplink.

## Citation Pipeline

### Backend: `[[cite:id]]value[[/cite]]`
Main agent emit citation tags trong synthesis markdown:
```
TVL Uniswap đạt [[cite:tvl-total-defillama]]$1.2B[[/cite]], tăng [[cite:tvl-7d-change-defillama]]2.1%[[/cite]] so với 7 ngày trước.
```

Citation ID format: `<metric>-<source>` (e.g. `tvl-total-defillama`, `price-usd-coingecko`).

### Frontend: Transform → Render
1. `preprocessMarkdown()` trong `markdown-text.tsx` transform:
   `[[cite:id]]value[[/cite]]` → `[cryptocite:id:value]`
2. `CITATION_REGEX` match `[cryptocite:id:value]` trong text
3. Render `<CryptoCitationInline citationId={id} displayValue={value} />`
4. Click citation → `SourceDetailPanel` slide-in với: reported value, provider, fetched timestamp, raw data

## Tool Infrastructure

### External API Dependencies

| Tool | API Provider | Rate Limit | Auth |
|------|-------------|------------|------|
| DeFiLlama (5 tools) | DeFiLlama | Unlimited | None |
| CoinGecko | CoinGecko | 30 req/min | None (demo) |
| GoPlus Security | GoPlus | 2000 req/day | None |
| CryptoPanic | CryptoPanic | Public | API key (optional) |
| CertiK Skynet (2 tools) | CertiK | Unknown | None |
| Nansen (3 tools) | Nansen | Tier-based | API key |
| Dune Analytics | Dune | Tier-based | API key |
| TokenInsight (2 tools) | TokenInsight | Unknown | API key |
| DexScreener (2 tools) | DexScreener | Unlimited | None |
| Etherscan | Etherscan | 5 req/sec | API key |

### Rate Limiter (`_rate_limiter.py`)
Shared utility cho external API rate limiting. `ProviderRateLimitMiddleware` enforce global min-interval giữa LLM calls.

### Fallback Strategy (NFR3)
Khi free APIs fail (429, timeout), sub-agents fallback sang `chainlens_deep_research` (web search-based) để vẫn có data cho synthesis.

## NFR Compliance

| NFR | Requirement | Implementation |
|-----|-------------|----------------|
| NFR-CS1 | Sub-agent prompts < 500 tokens | Verified with tiktoken trong spec files |
| NFR-CS2 | Parallel execution | LangGraph ToolNode chạy tất cả task() calls đồng thời |
| NFR-CS3 | Fallback web_search | chainlens_deep_research available trong mọi sub-agent |
| NFR-CS4 | Scoped tool lists | ALLOWED_TOOLS tuple per spec, runtime-filtered |
| NFR-CS5 | No DB deps cho crypto tools | Tất cả crypto tools có `requires=[]` |
| NFR-CS6 | Cache hit rate ≥ 70% | CryptoDataCacheMiddleware (Epic 10) — post-warmup |
| NFR-CS7 | Cache failure isolation | Graceful degradation → direct API call nếu DB/Redis down |

## Data Persistence Layer (Epic 10)

**Added:** 2026-04-29 | **ADR:** [ADR-001](../planning-artifacts/adrs/ADR-001-crypto-data-layer.md)

### Vị Trí Trong Pipeline

```
Sub-agent tool call
  ↓
SourceAttributionMiddleware   ← emit narration/events (unchanged)
  ↓
CryptoDataCacheMiddleware     ← intercept, check DB, write snapshot
  ↓
External API (nếu cache miss)
```

`CryptoDataCacheMiddleware` là middleware **transparent** — sub-agents không biết data đến từ cache hay API. `SourceAttributionMiddleware` tiếp tục fire events bình thường để FE hiển thị narration.

### Data Flow (cache hit)

```
defillama_analyst gọi get_defillama_protocol("uniswap")
  → CryptoDataCacheMiddleware:
      1. Lookup TOOL_CATEGORY_MAP → category = "defi_tvl", ttl = 3600s
      2. CryptoProjectResolver.resolve("uniswap") → project_id = 42
      3. DB query: SELECT data FROM crypto_data_snapshots
                   WHERE project_id=42 AND data_category='defi_tvl'
                   AND expires_at > NOW() ORDER BY fetched_at DESC LIMIT 1
      4. HIT → return {"tvl": 1200000000, "chains": [...], ...}
  → SourceAttributionMiddleware emit "data-orchestra-source-fetched" event
  → defillama_analyst nhận data bình thường
```

### Append-Only Timeline

Mỗi lần fetch = 1 row mới. Không UPDATE existing rows. Lợi ích:
- Audit trail đầy đủ: biết chính xác TVL của Uniswap tại mỗi thời điểm
- Hỗ trợ future features: "TVL trend 30 ngày", "Giá ETH theo giờ"
- Dedup bằng `data_hash` (SHA-256 của data JSON) — không tạo duplicate row nếu data không đổi

### CryptoProjectResolver — Multi-field Lookup

Các tools dùng identifiers khác nhau → resolver normalize thành canonical `project_id`:

| Tool | Identifier Type | Example |
|------|----------------|---------|
| DeFiLlama | `protocol_slug` | `"uniswap"` |
| CoinGecko | `token_id` (slug) | `"ethereum"` |
| DexScreener | `chain + token_address` | `"ethereum/0xC02..."` |
| GoPlus | `contract_address` | `"0xC02..."` |
| Nansen/TokenInsight | `token_symbol` | `"ETH"` |

Auto-create: nếu project chưa tồn tại → insert vào `crypto_projects` với partial info, enrich later.

### Feature Flags

| Flag | Default | Effect |
|------|---------|--------|
| `WHALE_TRACKER_ENABLED` | false | Enable/disable whale_tracker sub-agent |
| `RESUMABLE_RUNS_ENABLED` | true | Enable/disable background agent execution |
| `CRYPTO_DATA_CACHE_ENABLED` | false | Enable/disable CryptoDataCacheMiddleware (Epic 10) |
