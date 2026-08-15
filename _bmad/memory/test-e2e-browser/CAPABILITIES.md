# Capabilities

## Built-in

| Code | Name | Description | Source |
| :--- | :--- | :--- | :--- |
| [debug-failure] | Debug Test Failure | Rapidly diagnose root causes for failing tests, Zero-cache 401s, hydration issues, and backend errors. | `references/debug-failure.md` |
| [generate] | Generate Test Script | Produce production-ready, deterministic Playwright test code using Nowing merged-fixtures architecture. | `references/generate-script.md` |
| [inspect] | Inspect DOM & Network | Discover resilient selectors (getByRole, data-testid), analyze DOM accessibility tree, and audit UI state transitions. | `references/inspect-dom.md` |
| [observe] | Observe State | Maintain high-fidelity monitoring of DOM snapshots, visual screenshots, console logs, and network requests. | `references/observe-state.md` |
| [pilot] | Pilot Actions | Execute precise, deterministic user interactions on the live browser (navigate, click, type, fill forms). | `references/pilot-actions.md` |
| [verify-sse] | Verify SSE & Streams | Verify real-time SSE chat streaming, incremental token chunks, tool call progression, heartbeats, and citation events. | `references/verify-sse.md` |

## Learned

_Capabilities added by the owner over time. Prompts live in `capabilities/`._

| Code | Name | Description | Source | Added |
| :--- | :--- | :--- | :--- | :--- |

## How to Add a Capability

Tell me "I want you to be able to do X" and we'll create it together.
I'll write the prompt, save it to `capabilities/`, and register it here.
Next session, I'll know how.
Load `references/capability-authoring.md` for the full creation framework.

## Tools

Prefer crafting deterministic browser flows and tests via Playwright MCP & Chrome MCP.

### Available MCP Tools
- `playwright`: `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_fill_form`, `browser_type`, `browser_take_screenshot`, `browser_console_messages`, `browser_network_requests`, `browser_wait_for`
- `chrome-mcp`: Direct Chrome session inspection
