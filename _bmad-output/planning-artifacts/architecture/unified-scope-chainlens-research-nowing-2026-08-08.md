# Unified Architecture Proposal: chainlens-research + Nowing

**Date:** 2026-08-08  
**Author:** Winston (System Architect)  
**Scope:** Scope boundary between `chainlens-research` (standalone MCP/HTTP research service) and `Nowing` (workspace intelligence platform)

---

## Executive Summary

After reviewing PRDs, epics, architecture spines, and code from both projects:

- **No critical duplication exists** if the documented scope is respected.
- `chainlens-research` is the **universal research engine** (Brave/SearXNG → extract → reason → cite).
- `Nowing` is a **workspace intelligence consumer** that calls `chainlens-research` for deep web research.
- The perceived overlap (proxy, search, SearXNG, cache, index) comes from **naming, not function**.

This proposal locks the boundary, identifies one cleanup action, and defines the architecture for both services.

---

## What the Documents Actually Say

### chainlens-research (standalone service)

- **Product:** MCP server + HTTP API (`https://research-api.chainlens.net`)
- **Tools:** `chainlens_ping`, `chainlens_search`, `chainlens_ask`, `chainlens_reason`, `chainlens_research`, `chainlens_chat_history`
- **Search:** Brave primary → SearXNG fallback
- **State:** Stateless; no proxy, cache, or index layer of its own
- **Output:** SSE block protocol (`block`, `updateBlock`, `error`, `done`)
- **Contract:** `POST /api/v1/search` is the canonical H1 integration surface

### Nowing

- **Product:** Knowledge intelligence platform (workspaces, connectors, chat, automation, deliverables)
- **Owns:**
  - Workspace RAG (PostgreSQL + pgvector)
  - Anti-bot proxy for scraping (`app/utils/proxy/`)
  - ETL/indexing cache (`app/etl_pipeline/cache/`, `app/indexing_pipeline/cache/`)
  - Built-in scrapers, OAuth/MCP connectors, chat runtime, automations
- **Consumes:** `chainlens-research` for deep web research (FR-24)
- **Explicitly does NOT own:**
  - SearXNG integration (AD-DEFER-7)
  - General web index / crawl-at-scale
  - Competing research engine

---

## The Overlap Myth

| Word | chainlens-research | Nowing | Verdict |
|------|-------------------|--------|---------|
| **Proxy** | None | Anti-bot scraping proxy (BSL tier) | Different purpose, not duplicate |
| **Search** | Web search (Brave/SearXNG) + LLM synthesis | Hybrid KB search on workspace content | Different scope — Nowing consumes chainlens-research for web |
| **SearXNG** | Internal fallback only | NOT integrated | No duplicate — Nowing does not run SearXNG |
| **Cache** | None (stateless) | ETL/indexing cache + Redis + Zero sync | Different layer, not duplicate |
| **Index** | None (uses external search APIs) | pgvector on user/connector content | Different domain, not duplicate |

**Conclusion:** The only real overlap is that both touch "research" — one as engine, one as consumer.

---

## Proposed Unified Architecture

### Layer Model

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 2: Consumer                                                  │
│  ┌──────────────┐                                                   │
│  │    Nowing    │                                                   │
│  │ (workspace)  │                                                   │
│  └──────┬───────┘                                                   │
│         │                                                           │
│         │ POST /api/v1/search (SSE)                                 │
│         │ MCP tools (future if needed)                              │
├─────────┼───────────────────────────────────────────────────────────┤
│  Layer 1│  Research Engine                                          │
│         │    chainlens-research                                     │
│         │    ┌──────────────┐                                       │
│         │    │ Brave Search │                                       │
│         │    │ SearXNG      │ ── fallback                           │
│         │    └──────┬───────┘                                       │
│         │           ▼                                               │
│         │    ┌──────────────┐                                       │
│         │    │ Extract      │                                       │
│         │    │ Reason       │                                       │
│         │    │ Cite         │                                       │
│         │    └──────┬───────┘                                       │
│         │           ▼                                               │
│         │    SSE / MCP Response                                     │
├─────────┼───────────────────────────────────────────────────────────┤
│  Layer 0│  Web Search Providers                                     │
│         │    Brave, SearXNG (fallback)                              │
└─────────┴───────────────────────────────────────────────────────────┘

Nowing Domain-Specific Data:
- workspace RAG (pgvector)
- ETL cache
- anti-bot scraping proxy
```

### Ownership Matrix

| Capability | chainlens-research owns | Nowing owns |
|-----------|------------------------|-------------|
| Web search providers (Brave/SearXNG) | ✅ Only caller | ❌ |
| Deep research pipeline | ✅ | ❌ |
| Extraction/citations | ✅ | ❌ |
| MCP/HTTP interface | ✅ | ❌ |
| Workspace RAG index | ❌ | ✅ |
| User document index | ❌ | ✅ |
| Anti-bot scraping proxy | ❌ | ✅ |
| ETL/indexing cache | ❌ | ✅ |
| Billing/quotas for research usage | ❌ | ✅ |

### Data Flow

```
User (Nowing)
    │
    ▼
[Workspace RAG search] ── local content first
    │
    ▼ (if web research needed)
POST chainlens-research /api/v1/search
    │
    ▼
chainlens-research:
  Brave Search → if fail → SearXNG
    │
    ▼
  Extract pages
    │
    ▼
  Multi-step reasoning / LLM synthesis
    │
    ▼
  Return SSE with citations + usage
    │
    ▼
Nowing renders response, charges user, stores in memory
```

---

## Scope Rules (Architecture Decisions)

### AD-UR-01: chainlens-research is the only web search caller
- Only `chainlens-research` may call Brave, SearXNG, or other raw web search providers.
- Nowing must call `chainlens-research`, not search providers directly.

### AD-UR-02: chainlens-research remains stateless
- `chainlens-research` does not own cache or index.
- If semantic cache is needed to hit latency/cost targets, it is added **inside** `chainlens-research` and exposed transparently to consumers.

### AD-UR-03: Nowing does not build web index or SearXNG
- Reaffirm AD-DEFER-7 / NG-1: Nowing does not own a web index or crawl-at-scale.
- SearXNG is `chainlens-research` internal fallback, not a Nowing connector.

### AD-UR-04: Nowing owns its workspace data
- Nowing owns workspace content, embeddings, and user memory.
- No shared domain index between the two projects.

### AD-UR-05: Proxy is purpose-specific
- Nowing anti-bot proxy is for scraping (BSL tier).
- `chainlens-research` has no proxy; if it needs one later, it is internal to the research service.

---

## Cleanup Actions

### Nowing
1. **Remove or fully lock deprecated search connectors** (`SearXNG`, `Serper`, `Tavily`, `Baidu`)
   - If they exist as dead code, delete to avoid scope drift.
   - If needed for legacy, gate behind feature flag and document as deprecated.
2. **Rename `app/utils/proxy/` to `app/utils/scraper_proxy/`** (optional but recommended)
   - Prevents confusion with research proxy.
3. **Document the contract in ARCHITECTURE-SPINE**
   - Add AD-UR-01 through AD-UR-05.

### chainlens-research
1. **Add a `/health` endpoint and expose version**
   - Improves observability for Nowing consumers.
2. **Consider adding semantic cache (future)**
   - Only if latency/cost NFRs fail. Keep outside consumer platforms.
3. **Do not add anti-bot proxy or web index**
   - Violates the stateless research engine model.

---

## When This Architecture Would Break

| Scenario | Risk |
|----------|------|
| `chainlens-research` latency/cost fails NFRs | Add cache inside `chainlens-research`, not in Nowing |
| `chainlens-research` needs anti-bot for blocked sites | Add proxy inside `chainlens-research`, not reuse Nowing scraper proxy |
| Nowing wants self-host deep research (Phase 2) | Run separate `chainlens-research` instance; Nowing remains consumer |

---

## Final Verdict

**The current architecture is already reasonable.** The perceived duplication is mostly naming confusion. The only action needed is:

1. Clean up deprecated search connectors in Nowing.
2. Lock `chainlens-research` as the sole web search caller.
3. Document the unified scope in Nowing's ARCHITECTURE-SPINE.

No restructuring of `chainlens-research` or `Nowing` is required.
