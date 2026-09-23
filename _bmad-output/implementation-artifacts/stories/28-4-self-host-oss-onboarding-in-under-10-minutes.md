---
story_key: 28-4-self-host-oss-onboarding-in-under-10-minutes
status: done
epic: 28
---

# Story 28.4: Self-Host OSS Onboarding in Under 10 Minutes

**Status:** `done`  
**Epic:** Epic 28 — Self-Host Trust, Data Portability & Legal Readiness

## Story

As a developer evaluating Nowing,  
I want to self-host the open-core with `docker compose` and have a working workspace with local or remote LLM/embedding in under 10 minutes,  
so that I can trust the product and try it without a cloud account.

## Acceptance Criteria

- **Given** a fresh Linux, macOS, or Windows WSL2 machine with Docker installed, **When** the user runs `curl -fsSL .../install.sh | bash`, **Then** within 10 minutes Postgres, Redis, backend, frontend, and MCP server are healthy and the web UI is reachable at `http://localhost:3000`.
- **Given** a host with existing Postgres/Redis on default ports, **When** the install script detects the conflict, **Then** it prompts for alternative ports and updates `.env` + `docker-compose` accordingly.
- **Given** the install script runs, **When** the user has no OpenAI/Anthropic key, **Then** the script detects and offers a local embedding/LLM option (e.g. Ollama with `nomic-embed-text` + `llama3.1`) and sets `LOCAL_MODEL=true` so core memory features work offline.
- **Given** a first-time user opens the web UI, **When** they create an account and ask the agent to remember a fact, **Then** `nowing_remember` writes to `Memory`, `nowing_recall` returns it, and the aha moment happens without cloud dependency.

## Dev Notes

- Install script: `scripts/self_host_install.sh` (or equivalent)
- Local model path: Ollama fallback for `nomic-embed-text` + `llama3.1`
- Cloud bridge: optional `NOWING_CLOUD_API_URL` + `NOWING_SELF_HOST_API_KEY`
- FR-98 · AR-14 · RS-13 · INV-28.3 · AD-28.4

## Verification

- Route: `app/routes/self_host_research.py`
- Documentation: README quick-start rewritten for local model path
- CI smoke test nightly on fresh Ubuntu VM
