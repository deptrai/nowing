# Epic 32 Context: Browser Operator Runtime, Interactive Takeover & CDP Lifecycle

<!-- Compiled from planning artifacts and architectural review. Edit freely. -->

## Goal

Provide a hardened, fail-fast browser operator runtime with live human takeover synchronization and robust Chrome DevTools Protocol (CDP) lifecycle management. This eliminates worker process hanging, stale SSE streaming, and zombie mission resource leakage when users disconnect DevTools, close target tabs, or abandon interactive takeover challenges.

## Stories

- Story 32.2: Chrome Extension chrome.debugger.onDetach Recovery, Fail-Fast Signaling & Reconnection
- Story 32.1: HumanLiveTakeoverPopover Auto-Abort Sweeper & Timeout Scheduler

## Requirements & Constraints

- **Fail-Fast on Detach:** When `chrome.debugger.onDetach` fires (user clicks "Cancel" in browser debugger infobar, closes tab, or navigates to restricted internal URL), the extension must immediately notify the backend via `/dsh/cdp/result` with error code `DEBUGGER_DETACHED` and `requires_human: false` to unblock waiting workers in <200ms instead of waiting for 60s timeout.
- **Clean Socket & Debuggee Cleanup:** The extension's `CdpBridge` must reset `activeDebuggeeTabId = null` and detach any remaining listener on `onDetach` without throwing unhandled exceptions.
- **Mission Abort on Orphaned Detach:** If a detachment happens during an active CDP crawl node, the worker must catch the detachment result, transition the step to cancelled/error, and safely abort or retry per policy.
- **Backward Compatibility:** Maintain existing SSE protocol on `/dsh/cdp/stream` and POST payload on `/dsh/cdp/result`.

## Technical Decisions

- **Extension Lifecycle:** Register `chrome.debugger.onDetach.addListener` in `nowing_browser_extension/background/cdp-bridge.ts`. Track `activeDebuggeeTabId` and `activeMissionId`.
- **Backend Error Envelopes:** Handle `DEBUGGER_DETACHED` in `dsh_routes.py` and `dsh_worker_browser_operator.py` to abort the `blpop` wait loop immediately and raise a specific exception (`CdpDebuggerDetachedError`).
- **Idempotent Detach:** Ensure `detachDebugger()` checks whether the tab is already detached to avoid runtime errors from Chrome extension API.

## Cross-Story Dependencies

- Builds on Story 24.8 Browser Operator CDP Bridge (`nowing_browser_extension/background/cdp-bridge.ts`, `nowing_backend/app/routes/dsh_routes.py`, `nowing_backend/app/tasks/dsh_worker_browser_operator.py`).
- Story 32.2 (onDetach) runs first as the foundational lifecycle safety net; Story 32.1 (takeover reaper) builds upon the timeout lifecycle.
