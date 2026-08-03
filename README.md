<a href="https://www.nowing.com/"><img width="1584" height="396" alt="Nowing — open-core AI research workspace with a hosted deep-research engine" src="https://github.com/user-attachments/assets/9361ef58-1753-4b6e-b275-5020d8847261" /></a>



<div align="center">
<a href="https://discord.gg/ejRNvftDp9">
<img src="https://img.shields.io/discord/1359368468260192417" alt="Discord">
</a>
<a href="https://www.reddit.com/r/Nowing/">
<img src="https://img.shields.io/reddit/subreddit-subscribers/Nowing?style=social" alt="Reddit">
</a>
</div>

<div align="center">

[English](README.md) | [Español](README.es.md) | [Português](README.pt-BR.md) | [हिन्दी](README.hi.md) | [简体中文](README.zh-CN.md)

</div>
<div align="center">
<a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter%2FNowing | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</div>

# Nowing: Open-Core Research Memory for AI Agents

> **Nowing is open-core research memory for AI agents — it remembers what it went and found, not just what you told it.**

Nowing is a **self-hosted research workspace with long-term memory for AI agents and teams**, powered by an **Apache-2.0 core** and a **hosted deep-research engine**. Your agents research the live web with structured data from **Reddit, YouTube, Instagram, TikTok, Amazon, Google Maps, Google Search, and any page on the open web**, through one **REST API** or **MCP server**. Scheduled and event-triggered agents turn what they find into briefs and alerts, and a built-in knowledge base keeps every finding searchable with citations.

> [!NOTE]
> **📢 A note for our long-term research memory users**
>
> For the past couple of months we built Nowing as a workspace that turns research into durable, retrievable memory, and that chapter earned us a community we are genuinely proud of. Agentic tools like Claude, OpenCode, Hermes, and OpenClaw have now proven that agents are the future, and reasoning over a static index is becoming something every capable agent does out of the box. What agents still lack is **live data from the places where answers actually live, and the workflows around it**. That is where we are pointing all of our energy: giving agents the primitives to research the open web.
>
> **Nothing you rely on is going away.** Your knowledge base, chat with citations, reports, podcasts, presentations, automations, and collaborative chats all keep working, and self-hosting the Apache-2.0 core stays free. The hosted deep-research engine uses an optional cloud API key. Read the full announcement on [our changelog](https://www.nowing.com/changelog).

## Table of contents

- [Why agents need Nowing](#why-agents-need-nowing)
- [Live data connectors](#live-data-connectors)
- [Quick start](#quick-start)
- [Everything else in the box](#everything-else-in-the-box)
- [How Nowing compares](#how-nowing-compares)
- [Roadmap](#roadmap)
- [Contribute](#contribute)

## Why agents need Nowing

Ask any capable agent "what is Reddit saying about this product since launch?" or "what do the reviews of these ten places actually complain about?" and it has nowhere trustworthy to look. Official platform APIs are rate-limited, priced for enterprises, or missing entirely; scraping plumbing is brittle; and driving a browser with an LLM burns minutes and tokens per page. Nowing gives agents the primitives instead:

- **One typed surface for wherever the data lives.** Every connector is a REST endpoint returning structured JSON — posts, comments, transcripts, reviews, SERPs, pages. No rate-limit roulette, no HTML parsing, no browser loop.
- **An MCP server** that exposes every connector as a native tool (`nowing_reddit_scrape`, `nowing_google_search`, and more) to Claude, Cursor, or any agent framework.
- **An agent harness**, not just raw data: retries, structured output, and credit metering are built in, so agents go from a question to a cited brief without you building the plumbing.
- **Apache-2.0 core, self-hostable**, so your research stays on your own infrastructure. The deep-research engine is a hosted, metered service.

## Live data connectors

| Connector | What your agents get | Learn more |
|---|---|---|
| **Reddit** | Posts, comments, and subreddit streams without the official API's rate limits | [Reddit Scraper API](https://www.nowing.com/reddit) |
| **YouTube** | Videos, transcripts, and comment threads at scale | [YouTube Scraper API](https://www.nowing.com/youtube) |
| **Instagram** | Public profiles, posts, and reels without the Graph API | [Instagram Scraper API](https://www.nowing.com/instagram) |
| **TikTok** | Videos, comments, hashtags, and profiles without Research API approval | [TikTok Scraper API](https://www.nowing.com/tiktok) |
| **Google Maps** | Places, ratings, and reviews for local business research | [Google Maps Scraper API](https://www.nowing.com/google-maps) |
| **Google Search** | Live SERPs for search research and monitoring | [Google Search API](https://www.nowing.com/google-search) |
| **Amazon** | Public product data: prices, ratings, offers, sellers, and best-seller ranks | [Amazon Product API](https://www.nowing.com/amazon) |
| **Web Crawl** | Any page on the open web as clean, structured content | [Web Crawling API](https://www.nowing.com/web-crawl) |
| **External MCP Connectors** | Bring any MCP server to your agents, with one-click OAuth for Notion, Slack, Jira, and more | [External MCP Connectors](https://www.nowing.com/external-mcp-connectors) |

The connector catalog is growing beyond social platforms and search; every new source lands as a typed endpoint on the same API and MCP server.

Billing is pay as you go: connectors bill per item actually returned, crawls per page successfully fetched, and failed calls are never billed. Self-hosted installs run with billing off. See [pricing](https://www.nowing.com/pricing).

## Quick start

### Call a connector from code

Every connector is a REST endpoint you can call from any language with your Nowing API key:

```bash
curl -X POST "$NOWING_API_URL/workspaces/$WORKSPACE_ID/scrapers/reddit/scrape" \
  -H "Authorization: Bearer $NOWING_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "search_queries": ["your brand"],
    "community": "SaaS",
    "sort": "top",
    "time_filter": "week"
  }'
```

Each [connector page](https://www.nowing.com/connectors) has copy-paste examples in Python, JavaScript, Go, PHP, Ruby, Java, and C#.

### Give the tools to your agents over MCP

Add the Nowing MCP server to Claude, Cursor, or your own agent framework:

```json
{
  "mcpServers": {
    "nowing": {
      "url": "https://mcp.nowing.com/mcp",
      "headers": { "Authorization": "Bearer ${NOWING_API_KEY}" }
    }
  }
}
```

Your agent can now call every connector as a native tool. See the [Nowing MCP server](https://www.nowing.com/mcp-server) page for the full tool list, or run the server locally from [`nowing_mcp`](./nowing_mcp).

### Use the cloud

Go to [nowing.com](https://www.nowing.com), log in, and ask the agent for live web data in plain English. New accounts start with $5 of free credit and no subscription.

### Self-host for free

Run the entire platform, connectors, agents, automations, and the MCP server on your own infrastructure. Self-hosted installs ship with billing off, so scraping, crawling, and agent runs are limited only by your hardware and the model keys you bring.

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) must be installed and running.

For Linux/macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/nowing/Nowing/main/docker/scripts/install.sh | bash
```

For Windows:

```bash
irm https://raw.githubusercontent.com/nowing/Nowing/main/docker/scripts/install.ps1 | iex
```

The install script sets up [Watchtower](https://github.com/nicholas-fedor/watchtower) automatically for daily auto-updates. To skip it, add the `--no-watchtower` flag. For Docker Compose, manual installation, and other deployment options, see the [docs](https://www.nowing.com/docs/).

## Everything else in the box

The long-term research memory workspace that made Nowing a unique home for agent research is still here, and everything your agents gather lands in it.

**Knowledge base**

- Upload PDFs, Office docs, images, and audio, or sync **Google Drive, OneDrive, and Dropbox**. 50+ file formats supported.
- Hybrid semantic and full-text search with cited, Perplexity-style answers.

<p align="center"><img src="nowing_web/public/homepage/hero_tutorial/BQnaGif_compressed.gif" alt="Chat With Your PDFs and Docs" /></p>

**Deliverable studio**

- AI report generator with export to PDF, DOCX, HTML, LaTeX, EPUB, ODT, or plain text.
- Two-host AI podcasts from any document or folder in under 20 seconds.
- Editable slide decks, narrated video overviews, and AI image generation.

<p align="center"><img src="nowing_web/public/homepage/hero_tutorial/ReportGenGif_compressed.gif" alt="AI Report Generator" /></p>

**Automations**

- Run full agent turns on a schedule or in response to events, described in plain English, with results written back to Notion, Slack, Linear, and Jira.

**Team collaboration**

- Real-time collaborative AI chats with comments and mentions.
- RBAC with Owner, Editor, and Viewer roles.

<p align="center"><img src="nowing_web/public/homepage/hero_realtime/RealTimeChatGif.gif" alt="Collaborative AI Chat" /></p>

**Desktop app**

Native AI assistance in every application on your computer. Download from the [latest release](https://github.com/nowing/Nowing/releases/latest).

- **General Assist**: launch Nowing from any app with a global shortcut.
- **Quick Assist**: select text anywhere, then ask AI to explain, rewrite, or act on it.
- **Screenshot Assist**: capture any region of your screen and ask AI about it.
- **Watch Local Folder**: auto-sync a local folder to your knowledge base. Point it at your Obsidian vault to keep your notes searchable.

<p align="center"><img src="nowing_web/public/homepage/hero_tutorial/quick_assist.gif" alt="Quick Assist" /></p>

**No vendor lock-in**

- 100+ LLMs via the OpenAI spec and LiteLLM, including GPT-5.5, Claude Sonnet 5, and Gemini 3.1 Pro.
- 6,000+ embedding models and all major rerankers.
- Full local and private LLM support (vLLM, Ollama), so your data stays yours.

## Video Agent Sample

https://github.com/user-attachments/assets/012a7ffa-6f76-4f06-9dda-7632b470057a

## Podcast Agent Sample

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7

## How to collaborate in real time (Beta)

1. Go to the Manage Members page and create an invite.

   <p align="center"><img src="https://github.com/user-attachments/assets/40ed7683-5aa6-48a0-a3df-00575528c392" alt="Invite Members" /></p>

2. A teammate joins and that workspace becomes shared.

   <p align="center"><img src="https://github.com/user-attachments/assets/ea4e1057-4d2b-4fd2-9ca0-cd19286a285e" alt="Invite Join Flow" /></p>

3. Make a chat shared and work in it together in real time, with comments to tag teammates.

   <p align="center"><img src="nowing_web/public/homepage/hero_realtime/RealTimeCommentsFlow.gif" alt="Realtime Comments" /></p>

## How Nowing compares

Nowing is the only product with an Apache-2.0 core that combines long-term research memory with live-data primitives for agents. Here is how that stacks up against each class of tool.

**vs browser agents (Browserbase, Browser Use).** Browser agents drive a real browser with an LLM in the loop — the right tool when a task needs clicking, logging in, or filling forms. But most research is read-only retrieval, and for retrieval the LLM-in-a-browser loop costs you minutes and thousands of tokens per page. A Nowing connector call is one HTTP request: seconds, deterministic, and zero tokens spent deciding where to click.

**vs scraping APIs (Firecrawl).** Scraping APIs are great at turning a generic page into markdown, but a markdown blob still leaves your agent parsing structure out of prose, and they degrade on bot-protected platforms like Reddit, TikTok, and Instagram. Nowing connectors return platform-native structured items — posts, comments, transcripts, reviews — and bill only for items actually returned; failed calls are never billed.

**vs search APIs (Exa, Tavily, Parallel).** Search APIs answer from a web index, which is the right tool for "find me pages about X." They cannot pull a Reddit thread's comments, TikTok reactions, YouTube transcripts, or Google Maps reviews — the places where the answer often actually lives.

**vs scraper marketplaces (Apify).** Marketplaces give you thousands of community actors, each with its own schema, quality, and pricing. Nowing is one typed API and one MCP server with an agent harness and a research workspace behind it, and its core is Apache-2.0.

### How Nowing compares to consumer research tools

Most memory layers remember what you told them. **Nowing also remembers what it went and found.**

Nowing is not a better note-taking app; it is an open-core research workspace that turns live-web research into durable, citable memory for agents and teams.

| | Self-host (free) | Cloud (pay as you go) |
|---|---|---|
| **Memory layer + 4 MCP tools** | ✅ | ✅ |
| **Knowledge base + hybrid search + citations** | ✅ | ✅ |
| **8 platforms / 14 scraping verbs** (Reddit/YouTube/TikTok/Instagram/Google Search+Maps/Amazon/web crawl) | ✅ (BSL 1.1 crawler engine) | ✅ |
| **Chat, deliverables, automations** | ✅ | ✅ |
| **5 client surfaces** (web/desktop/extension/Obsidian/MCP) | ✅ | ✅ |
| **Deep multi-step open-web research** | Phase 1: ❌ · Phase 2: 💳 metered | ✅ |

**License at a glance:**
- Core (everything outside `nowing_backend/app/proprietary/`): **Apache-2.0** — free to use and modify.
- Crawler engine (`nowing_backend/app/proprietary/**`): **BSL 1.1** — free to run, including production, but cannot be resold as a hosted/managed service.
- Deep-research engine: **closed-source, hosted** — cloud-only in Phase 1.

## Feature requests and future

**Nowing is actively being developed.** While it's not yet production-ready, you can help us speed up the process.

Join the [Nowing Discord](https://discord.gg/ejRNvftDp9) and help shape the future of Nowing!

## Roadmap

Stay up to date with our development progress and upcoming features. Check out our public roadmap and contribute your ideas or feedback:

**Roadmap Discussion:** [Nowing 2026 Roadmap](https://github.com/nowing/Nowing/discussions/565)

**Kanban Board:** [Nowing Project Board](https://github.com/users/MODSetter/projects/3)

## Contribute

All contributions welcome, from stars and bug reports to backend improvements. See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

Thanks to all our Surfers:

<a href="https://github.com/nowing/Nowing/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=nowing/Nowing" />
</a>

## Star History

<a href="https://www.star-history.com/#nowing/Nowing&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=nowing/Nowing&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=nowing/Nowing&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=nowing/Nowing&type=Date" />
 </picture>
</a>

---
---
<p align="center">
    <img 
      src="https://github.com/user-attachments/assets/329c9bc2-6005-4aed-a629-700b5ae296b4" 
      alt="Catalyst Project" 
      width="200"
    />
</p>

---
---
