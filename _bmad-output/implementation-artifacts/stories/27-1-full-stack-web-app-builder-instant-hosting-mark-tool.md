---
story_key: "27-1"
epic: "epic-27"
story: "27.1"
title: "Full-Stack Web App Builder, 1-Click Hosting *.nowing.space & Design View Mark Tool"
status: "ready-for-dev"
---

# Story 27.1: Full-Stack Web App Builder, 1-Click Hosting *.nowing.space & Design View Mark Tool

## Story Overview

As a Nowing user,
I want to describe a web app in natural language and have the agent generate, preview, and deploy it to `https://[app].nowing.space`,
So that I can ship a working full-stack application without writing code.

## Architectural Invariants

- **AD-113:** Agent generates Next.js/React + Tailwind CSS into `/workspace/web-app`; deployment uses a Dockerfile template + Traefik dynamic SSL routing.
- **AD-114:** Iframe preview injects a Bounding Box Selector; clicking an element extracts DOM selector and AST-mutates the corresponding JSX.

## Acceptance Criteria

1. **LLM Web App Generation**
   - **Given** a natural-language description of a web app,
   - **When** the builder runs,
   - **Then** a Next.js + Tailwind project is written to `/workspace/web-app` and a preview URL is returned.

2. **1-Click Publish to `*.nowing.space`**
   - **Given** the generated app passes validation,
   - **When** the user clicks `Publish`,
   - **Then** the app is deployed to `https://[app-name].nowing.space` with a valid SSL certificate.

3. **Custom CNAME / Domain Connect**
   - **Given** a user wants to use a custom domain,
   - **When** they configure a CNAME,
   - **Then** Traefik dynamically routes the domain to the app container.

4. **Design View Mark Tool**
   - **Given** the Mark Tool is active on a web preview,
   - **When** the user clicks an element,
   - **Then** the tool captures a bounding box selector and updates the JSX AST accordingly.

## Consequences

- New backend service: `app/services/web_builder/`.
- New Dockerfile template: `docker/web-app.Dockerfile`.
- Traefik dynamic config + wildcard `*.nowing.space` DNS.
- Workspace-scoped app registry.
