# Nowing MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes
Nowing to MCP clients like **Claude Code**, **Cursor**, and **Claude Desktop**.
It talks to a Nowing backend purely over its REST API using a Nowing API
key — it imports no backend code.

Connect it two ways:

- **Hosted** (recommended) — point your client at `https://mcp.nowing.com/mcp`
  and pass your API key in a header. Nothing to install or keep running.
- **Self-host (stdio)** — run the server yourself against any backend (cloud or
  your own). Best for self-hosters and clients without remote-server support.

## Tools

**Search-space selector**
- `nowing_list_workspaces` — list the workspaces (search spaces) you can access
- `nowing_select_workspace` — pick the active workspace by name or id

**Scrapers (all platforms)**
- `nowing_web_crawl`, `nowing_google_search`, `nowing_reddit_scrape`,
  `nowing_youtube_scrape`, `nowing_youtube_comments`,
  `nowing_instagram_scrape`, `nowing_instagram_details`,
  `nowing_tiktok_scrape`, `nowing_tiktok_comments`,
  `nowing_tiktok_user_search`, `nowing_tiktok_trending`,
  `nowing_google_maps_scrape`, `nowing_google_maps_reviews`
- `nowing_list_scraper_runs`, `nowing_get_scraper_run` — retrieve past
  results in full (useful when a large result was truncated inline)

**Knowledge base**
- `nowing_search_knowledge_base` — semantic + keyword search over stored content
- `nowing_list_documents`, `nowing_get_document`
- `nowing_add_document`, `nowing_upload_file`
- `nowing_update_document`, `nowing_delete_document`

Workspace-scoped tools default to the active workspace; pass `workspace` (a name
or id) to override for a single call. Ids never need to be typed by hand — the
model carries them between calls.

## Get an API key

1. Nowing → **API Playground → API Keys**: create a personal key (`nw_pat_…`).
   It is shown only once.
2. Toggle **API key access** on for the workspace(s) you want to use.

## Connect (hosted)

Point your client at the hosted server and send the key as a Bearer token. For
clients that read an `mcpServers` map (Cursor, Claude Desktop, and others):

```json
{
  "mcpServers": {
    "nowing": {
      "url": "https://mcp.nowing.com/mcp",
      "headers": { "Authorization": "Bearer nw_pat_your_key_here" }
    }
  }
}
```

Claude Code, from a terminal:

```bash
claude mcp add --transport http nowing https://mcp.nowing.com/mcp \
  --header "Authorization: Bearer nw_pat_your_key_here"
```

Most MCP clients accept this `url` + `headers` form; check your client's docs for
its exact remote-server field.

## Self-host (stdio)

Run the server yourself when you host your own backend or use a client without
remote support. It uses [uv](https://github.com/astral-sh/uv):

```bash
cd nowing_mcp
uv sync
uv run python -m mcp_server.selfcheck   # verify tools register correctly
```

Then add it to your client. Cursor (`~/.cursor/mcp.json` or a project
`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "nowing": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/Nowing/nowing_mcp", "python", "-m", "mcp_server"],
      "env": {
        "NOWING_BASE_URL": "http://localhost:8000",
        "NOWING_API_KEY": "nw_pat_your_token_here"
      }
    }
  }
}
```

Claude Code:

```bash
claude mcp add nowing \
  -e NOWING_BASE_URL=http://localhost:8000 \
  -e NOWING_API_KEY=nw_pat_your_token_here \
  -- uv run --directory /absolute/path/to/Nowing/nowing_mcp python -m mcp_server
```

Claude Desktop: add the same `mcpServers` block as Cursor to
`claude_desktop_config.json` (Settings → Developer → Edit Config).

## Configuration

See `.env.example`. For self-host, secrets are passed as environment variables by
the client; never commit tokens.

## Backend dependency

`nowing_search_knowledge_base` calls `POST /api/v1/documents/search-semantic`,
a thin endpoint that exposes the backend's existing hybrid retriever over REST.
All other tools use pre-existing Nowing endpoints.
