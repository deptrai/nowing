# Nowing — Project Overview

**Nowing is open-core research memory for AI agents — it remembers what it went and found, not just what you told it.**

It is a self-hosted research workspace with long-term memory for AI agents and teams, backed by an Apache-2.0 core and a hosted deep-research engine.

## What it does

- **Long-term research memory:** facts, decisions, observations, and research threads are stored with source citations, confidence scores, and version history.
- **Live-web data connectors:** Reddit, YouTube, Instagram, TikTok, Amazon, Google Maps, Google Search, and generic web crawl — exposed through a single typed REST API and MCP server.
- **Agent workspace:** multi-agent chat with citations, deliverables (reports, podcasts, videos, images), and automations that can write back to Notion, Slack, Linear, and Jira.
- **Multi-surface:** web app, desktop (Electron), browser extension, Obsidian plugin, and MCP server.

## License and self-host vs cloud

| Layer | Scope | License | Self-host |
|---|---|---|---|
| Core | Everything outside `nowing_backend/app/proprietary/` | Apache-2.0 | ✅ free |
| Crawler engine | `nowing_backend/app/proprietary/**` | BSL 1.1 (free to run, including production; cannot resell as hosted/managed service) | ✅ free |
| Deep-research engine | Hosted cloud service | Closed-source | Phase 1: ❌ (returns `engine_unavailable`) · Phase 2: metered |

## For more

- [Documentation index](./index.md)
- [Source tree analysis](./source-tree-analysis.md)
- [Backend architecture](./architecture-backend.md)
- [Web architecture](./architecture-web.md)
- [Integration architecture](./integration-architecture.md)
