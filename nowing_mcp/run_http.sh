#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")"
export NOWING_MCP_TRANSPORT=http
export NOWING_MCP_PORT=8765
export NOWING_BASE_URL=http://localhost:4445
export NOWING_API_KEY='nw_pat_fRzBaw88DhcV9NMw8yRlX6Cjvjopd5jr3xTp11t3LOY'
export NOWING_WORKSPACE='My Workspace'
exec uv run nowing-mcp
