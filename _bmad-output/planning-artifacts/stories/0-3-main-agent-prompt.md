---
storyId: 0.3
storyTitle: Main Agent Crypto Orchestration Prompt
epicParent: epic-00-crypto-foundation
dependsOn: [Story 0.2]
blocks: [Story 0.4, Epic 9 Phase 1]
relatedFRs: [FR33 Parallel Orchestration, FR34 Smart Agent Selection]
relatedNFRs: [NFR-CS2, NFR-Q4]
priority: P0 (BLOCKING)
estimatedEffort: 2-3 days
status: ready-for-dev (blocked on 0.2)
createdAt: 2026-04-23
author: Mary (Strategic Business Analyst)
---

# Story 0.3: Main Agent Crypto Orchestration Prompt

## User Story

**As a** main agent,
**I want** clear instructions on when and how to spawn crypto sub-agents in parallel (or selectively),
**So that** I can coordinate multiple specialists efficiently for comprehensive analysis — without over-spawning when user only asks 1 narrow question.

---

## Context

Story 0.1 + 0.2 implement infrastructure (tools + sub-agents). Story 0.3 teach main agent **WHEN to use them** through orchestration prompt — đây là phần quyết định Quality Gate NFR-Q4 (speed) và NFR-Q2 (avoid wasted parallel spawn).

**Key behavior to teach**:
1. ✅ Spawn parallel khi user hỏi "phân tích toàn diện" / "comprehensive analysis"
2. ✅ Spawn 1-2 agents khi user hỏi câu cụ thể ("kiểm tra security X", "TVL của Y")
3. ❌ KHÔNG spawn khi câu đơn giản ("giá BTC?") — gọi tool trực tiếp
4. ❌ KHÔNG spawn cả 5 agents khi chỉ cần 2

---

## Deliverables

### 📝 File to Modify

#### `nowing_backend/app/agents/new_chat/system_prompt.py` (47KB)

**Action**: Tìm crypto-related section (hoặc thêm mới nếu chưa có) và update với content sau.

#### Section đề xuất: "## Crypto Analysis Orchestration"

```markdown
## Crypto Analysis Orchestration

You có 4 crypto specialist sub-agents có thể spawn qua `task()` tool. Sử dụng intelligently — KHÔNG spawn agent khi tool trực tiếp đủ.

### Agent Lookup Table

| Agent | Chuyên môn | Trigger keywords (VN/EN) |
|-------|------------|-------------------------|
| `defillama_analyst` | DeFi TVL, yields, protocols, stablecoins, bridges | "TVL", "yield farm", "DeFi protocol", "lending pool", "DEX volume" |
| `sentiment_analyst` | Fear & Greed Index, Reddit community sentiment | "sentiment", "Fear Greed", "community mood", "tâm lý thị trường", "FOMO" |
| `news_analyst` | Crypto news, project announcements, CoinGecko info | "tin tức", "news", "announcement", "thông báo", "press release" |
| `smart_contract_analyst` | Contract security, honeypot check, audit status, holder distribution | "security check", "audit", "honeypot", "rug pull", "contract review", "kiểm tra hợp đồng" |

### Orchestration Decision Tree

**Step 1**: Check intent của user query.

**Step 2**: Apply rules theo thứ tự:

#### Rule A — Direct tool call (NO sub-agent)
**When**: User hỏi câu đơn giản về 1 data point có thể lấy trực tiếp.
**Examples**:
- "Giá BTC bây nhiêu?" → call `get_live_token_data(symbol="BTC")` directly
- "TVL của Uniswap?" → call `get_defillama_protocol(protocol_slug="uniswap")` directly
- "F&G index hôm nay?" → call `get_cmc_sentiment(symbol="BTC")` directly

**Why**: Spawn sub-agent overhead (~2-3s + extra tokens) không justify cho query đơn giản.

#### Rule B — Single specialist spawn
**When**: User hỏi câu cần phân tích chuyên sâu 1 khía cạnh.
**Examples**:
- "Kiểm tra security của contract 0x..." → spawn `smart_contract_analyst`
- "Top yield farms cho USDC hiện tại" → spawn `defillama_analyst`
- "Tin tức gần đây về Solana" → spawn `news_analyst`

**Why**: Specialist có system prompt focused + structured output format.

#### Rule C — Parallel multi-agent spawn
**When**: User hỏi "phân tích toàn diện", "comprehensive analysis", "deep dive", "đánh giá X cho long position".
**Examples**:
- "Phân tích toàn diện $UNI" → parallel spawn: defillama + sentiment + news + smart_contract
- "Đánh giá $AAVE cho long-term hold" → parallel spawn 4 agents
- "Comprehensive analysis of Curve Finance" → parallel spawn 4 agents

**Action**: Issue **ALL** task() calls trong **CÙNG 1 response** (LangGraph sẽ batch parallel automatically). KHÔNG spawn tuần tự.

**Why**: Total time ≈ max(individual time) ≈ 30-45s, không phải sum 2-3 phút.

#### Rule D — Selective spawn (subset)
**When**: User mention nhiều khía cạnh nhưng KHÔNG full comprehensive.
**Examples**:
- "Token X có an toàn để hold không?" → spawn smart_contract + sentiment (skip defillama, news)
- "DeFi opportunity cho USDC, có rủi ro gì?" → spawn defillama + smart_contract (skip sentiment, news)

### Anti-Patterns (DO NOT DO)

❌ **Don't** spawn agents khi user chỉ hỏi giá hoặc 1 data point đơn giản
❌ **Don't** spawn agents tuần tự — luôn parallel khi cần multiple
❌ **Don't** spawn cả 5 agents (general_purpose + 4 crypto) cho mọi query
❌ **Don't** spawn 1 agent rồi spawn agent khác sau khi nhận response — batch upfront

### Examples — Good Orchestration

**Example 1: Comprehensive analysis**
```
User: "Phân tích toàn diện $UNI cho long position 6 tháng"

Main agent response (parallel batch in 1 LLM turn):
- task(agent="defillama_analyst", task="UNI DeFi metrics: TVL, yield, protocol breakdown")
- task(agent="sentiment_analyst", task="UNI community sentiment 30 days")
- task(agent="news_analyst", task="UNI recent news and announcements")
- task(agent="smart_contract_analyst", task="UNI token security check, holder distribution")

[Wait for all 4 results]
[Synthesize into structured response]
```

**Example 2: Direct tool**
```
User: "Giá UNI hiện tại?"
Main agent: call get_live_token_data(symbol="UNI") → return formatted answer
```

**Example 3: Single specialist**
```
User: "Token này có phải scam không? 0xabc..."
Main agent: task(agent="smart_contract_analyst", task="Security audit for 0xabc...")
```
```

---

## Acceptance Criteria

### AC1: Section added to system prompt

**Given** `system_prompt.py` được modify
**When** server load main agent prompt
**Then** prompt chứa section "Crypto Analysis Orchestration" với:
- Agent Lookup Table (4 agents)
- Orchestration Decision Tree (4 rules: A/B/C/D)
- Anti-Patterns
- 3 worked examples

### AC2: Comprehensive analysis triggers parallel spawn

**Given** user hỏi "Phân tích toàn diện $UNI"
**When** main agent xử lý
**Then** trace logs show 4 `task()` calls trong cùng 1 LLM response
**And** all 4 spawn trong cùng 1 LangGraph ToolNode step
**And** parallelism ratio < 1.3x (NFR-CS2)

### AC3: Simple query KHÔNG trigger spawn

**Given** user hỏi "Giá BTC?"
**When** main agent xử lý
**Then** main agent gọi `get_live_token_data(symbol="BTC")` trực tiếp
**And** KHÔNG spawn bất kỳ sub-agent nào
**And** response time < 5s (no sub-agent overhead)

### AC4: Single specialist spawn cho focused query

**Given** user hỏi "Kiểm tra security 0xabc..."
**When** main agent xử lý
**Then** main agent gọi `task(agent="smart_contract_analyst", ...)` only
**And** KHÔNG spawn 3 agents khác
**And** response chứa security check structured output

### AC5: Selective subset spawn

**Given** user hỏi "Token X an toàn để hold không?"
**When** main agent xử lý
**Then** main agent spawn 2 agents: `smart_contract_analyst` + `sentiment_analyst`
**And** KHÔNG spawn `defillama_analyst` hoặc `news_analyst`

### AC6: LLM follows lookup table consistently

**Given** suite 20 test queries (mix of Rule A/B/C/D)
**When** main agent xử lý mỗi query
**Then** ≥ 90% queries route đúng rule (manual classification)
**And** không có "over-spawning" (spawn agent khi không cần)
**And** không có "under-spawning" (skip parallel khi user yêu cầu comprehensive)

---

## Definition of Done (5 checkpoints)

- [ ] **DoD-1** Story 0.2 verified DONE (precondition)
- [ ] **DoD-2** `system_prompt.py` updated với "Crypto Analysis Orchestration" section
- [ ] **DoD-3** Token count check: thêm content ≤ 2000 tokens (overhead acceptable cho main prompt)
- [ ] **DoD-4** Manual test 20 queries — pass ≥ 90% routing accuracy
- [ ] **DoD-5** Integration test: parallel spawn case (Rule C) hits all 4 agents in 1 step

---

## Dev Notes

### Token Budget Cho Main Agent Prompt

Main agent prompt là 47KB hiện tại — thêm crypto section ~2-3KB (~1500-2000 tokens). Acceptable trong scope total prompt budget.

### Test Query Suite (20 queries)

| # | Query (VN) | Expected Rule | Agent(s) |
|---|-----------|---------------|----------|
| 1 | "Giá BTC?" | A | direct tool |
| 2 | "TVL của Aave?" | A | direct tool |
| 3 | "F&G index?" | A | direct tool |
| 4 | "Top 10 DeFi protocols by TVL" | B | defillama |
| 5 | "Sentiment thị trường crypto" | B | sentiment |
| 6 | "Tin tức về Solana tuần này" | B | news |
| 7 | "Audit contract 0x..." | B | smart_contract |
| 8 | "Phân tích toàn diện $UNI" | C | all 4 |
| 9 | "Comprehensive review of Curve" | C | all 4 |
| 10 | "Đánh giá $AAVE cho long position" | C | all 4 |
| 11 | "Token X có scam không?" | D | sc + sentiment |
| 12 | "DeFi yield USDC, rủi ro?" | D | defillama + sc |
| 13 | "Có news + sentiment về $LDO không" | D | news + sentiment |
| ... | (thêm 7 queries variations) | | |

### Common Pitfalls

1. ❌ **Don't** force LLM tuân chính xác Rule A/B/C/D — soft guidelines, LLM dùng judgment
2. ⚠️ **Watch for** over-fitting: nếu LLM spawn parallel CHO MỌI query có nhiều keywords → tighten Rule A examples
3. ⚠️ **Watch for** under-spawning: nếu LLM không spawn parallel khi user nói "toàn diện" → strengthen Rule C examples

---

## Traceability

| Requirement | Source | Fulfilled By |
|-------------|--------|--------------|
| FR33 Parallel orchestration | `prd.md` | AC2 |
| FR34 Smart agent selection | `prd.md` | AC3, AC4, AC5, AC6 |
| NFR-CS2 Parallel execution | `prd.md` + `epics.md` | AC2 |
| NFR-Q4 Speed | `prd.md` Quality Gates | AC3 (avoid overhead), AC2 (parallel) |

---

**Status**: ready-for-dev ✅ (blocked on Story 0.2)
**Next**: Stories 0.4-0.6 (testing) → Phase 1 Story 9.1.
