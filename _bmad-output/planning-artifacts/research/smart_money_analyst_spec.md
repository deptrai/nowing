# Technical Specification: `smart_money_analyst` Sub-Agent

**Epic:** 13 (Institutional Research Terminal)
**Story:** 13.1 (Entity Resolution & Smart Money Flow)
**Target File:** `nowing_backend/app/agents/new_chat/subagents/crypto/smart_money_analyst_spec.py`

## 1. Agent Persona & System Prompt

The system prompt is the core engine guiding the LLM to interpret on-chain flow data like a professional on-chain analyst. It must be under 500 tokens (NFR-CS1) and focus on logic rather than formatting.

```python
SMART_MONEY_ANALYST_NAME = "smart_money_analyst"
SMART_MONEY_ANALYST_DESCRIPTION = "Chuyên gia phân tích dòng tiền on-chain, theo dõi ví cá mập (smart money), gom nhóm thực thể (entity clustering) và nhận diện các giao dịch nội bộ (insider transactions)."

SMART_MONEY_ANALYST_PROMPT = """You are a world-class on-chain forensic analyst. Your goal is to track 'Smart Money' flows, identify entity clusters (Funds, Exchanges, Insiders), and detect accumulation/distribution phases.

CORE PRINCIPLES:
1. A single address is meaningless; focus on ENTITIES (clusters of addresses funded by the same source).
2. Large outflows from CEX to fresh wallets often indicate accumulation (Buy).
3. Large inflows to CEX from known whale entities indicate distribution (Sell).
4. Always cite your data sources (e.g., Nansen, Neo4j Graph).

WHEN ANALYZING A TOKEN OR ENTITY:
- Use `get_entity_labels` to identify who owns a wallet.
- Use `get_token_net_flow` to see the 24h/7d balance changes for Smart Money vs Retail.
- Use `get_related_wallets` to find sibling wallets in a cluster via gas-funding analysis.

Output your findings clearly, highlighting suspicious insider activities and net money flow trends."""
```

## 2. Tool Definitions & API Integration

The agent requires highly specific tools that interact with the newly proposed Kafka/Neo4j infrastructure and the Nansen API. These tools must be stateless (`requires=[]`) per NFR-CS4.

### Tool 1: `get_entity_labels(addresses: list[str])`
- **Purpose:** Resolves raw blockchain addresses into human-readable entity labels (e.g., "a16z", "Binance Hot Wallet 3", "MEV Bot").
- **Integration:** Calls Nansen API (`/v1/labels/addresses`).
- **Caching:** Uses Epic 10's `CryptoDataCacheMiddleware` to prevent redundant Nansen API calls (high cost).

### Tool 2: `get_token_net_flow(token_address: str, chain: str, time_window: str = "7d")`
- **Purpose:** Returns the net inflow/outflow of a token, categorized by entity type (Smart Money, Exchanges, Retail).
- **Integration:** Queries the internal Neo4j Graph Database (which aggregates the real-time Kafka streams).
- **Output:** `{"smart_money_net_usd": +5000000, "exchange_net_usd": -4500000, "retail_net_usd": -500000}`. (Smart money buying, exchanges depleting).

### Tool 3: `get_related_wallets(address: str, max_depth: int = 2)`
- **Purpose:** Performs entity clustering to find all wallets associated with a target address.
- **Integration:** Executes a Cypher query on Neo4j.
  *Cypher Example:* `MATCH (w1:Wallet {address: $address})-[r:FUNDED_GAS]->(w2:Wallet) RETURN w2`
- **Output:** Returns a list of associated wallets and the confidence score of the cluster.

## 3. LangGraph Orchestration & Parallelism

When a user asks: *"Phân tích dòng tiền Smart Money của token $PEPE trong tuần qua"*

1. **Intent Detection:** The Main Agent identifies the `smart_money_analyst` trigger based on the description.
2. **Spawn:** The LangGraph `ToolNode` spawns `smart_money_analyst`.
   - If the user asks for a *comprehensive analysis*, this agent runs in parallel (NFR-CS2) alongside `tokenomics_analyst` and `technical_analyst`.
3. **Execution Flow:**
   - The sub-agent calls `get_token_net_flow`.
   - It notices a massive $5M inflow to unknown addresses.
   - It calls `get_entity_labels` on those addresses. Nansen returns "Unknown".
   - It calls `get_related_wallets` and discovers these unknown addresses were gas-funded by a known "Wintermute" wallet.
4. **Synthesis:** The agent outputs a report: *"Dòng tiền cho thấy sự tích lũy mạnh. Dù các ví gom hàng chưa có nhãn, phân tích đồ thị gas funding cho thấy chúng có liên kết trực tiếp với quỹ Wintermute..."*

## 4. Technical Challenges & Risk Mitigation

- **Nansen API Costs & Rate Limits:** Nansen API is expensive and strict on rate limits. Epic 11's `TokenBucketRateLimiter` must be heavily enforced here. Fallback mechanism: If Nansen is unavailable, rely purely on internal Neo4j heuristics (less accurate but maintains uptime).
- **Neo4j Traversal Latency:** Deep graph traversals (depth > 3) can cause exponential slowdowns. Hardcode `max_depth=2` in the tool definition to prevent the LLM from executing queries that freeze the database.
- **Hallucination Control (NFR-Q2):** The prompt explicitly demands citing sources. We must parse the LLM output to ensure any claim of "a16z is buying" is directly backed by the tool response payload, otherwise, the Quality Gate fails.
