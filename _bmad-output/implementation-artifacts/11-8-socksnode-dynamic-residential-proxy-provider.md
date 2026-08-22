# Story 11.8 — SocksNode Dynamic Residential Proxy Provider & Multi-Account Sticky Binding

**Story ID:** 11.8  
**Epic:** 11 — Resilient Network & Proxy Pool Management  
**Status:** ready-for-dev  
**Owner:** DEV  
**Source:** `ARCHITECTURE-SPINE.md` (SocksNode Integration 2026-08-22) AD-SN-1 đến AD-SN-6, `technical-socksnode-proxy-platform-research-2026-08-22.md`, `src/proxy/**`, `nowing_backend/app/utils/proxy/**`.

---

## Story

As a **Core Crawler & Social Automation Engineer**,  
I want a **dedicated `SocksNodeProvider` and auto-detection preset in `DynamicTunnelProvider` for SocksNode Residential Network (`*.socksnode.com:9000`)**,  
So that **XActions and Nowing scrapers can dynamically control Geo-targeting (`-country-vn`), hold multi-account sticky IP sessions (`-session-fb_<id>-lifetime-86400`), automatically rotate on block, and block heavy resources (images/fonts) to save 80–89% bandwidth without leaking origin IPs.**

---

## Acceptance Criteria

### AC-1: SocksNode Provider Preset in `DynamicTunnelProvider` (Node.js)
* **Given** a SocksNode gateway URL matching `*socksnode.com` (e.g. `http://user:pass@sg.premium.socksnode.com:9000`)
* **When** `new DynamicTunnelProvider({ gatewayUrl })` or `createProxyProvider({ gatewayUrl })` is instantiated
* **Then** it auto-detects `provider: 'socksnode'`
* **And** it formats credentials by appending parameters to the **username** with hyphen delimiters:
  ```text
  ${baseUser}[-country-${country}][-city-${city}][-session-${sessionId}][-lifetime-${lifetimeSeconds}]
  ```
* **And** `password` remains strictly unchanged (the exact raw password).
* **And** `toPlaywrightProxy(proxy)` correctly separates `server` (`http://sg.premium.socksnode.com:9000`), `username`, and `password`.

### AC-2: Dedicated `SocksNodeProvider` Implementation (Python Backend)
* **Given** `nowing_backend/app/utils/proxy/providers/socksnode.py`
* **When** `SocksNodeProvider` is instantiated and registered in `registry.py` (`PROXY_PROVIDER="socksnode"`)
* **Then** it implements:
  - `get_proxy_url()`: returns basic rotating proxy URL.
  - `get_geo_proxy_url(country="vn")`: returns URL with `-country-vn`.
  - `get_sticky_proxy_url(session_id="fb_123", country="vn", lifetime_s=86400)`: returns URL with `-country-vn-session-fb_123-lifetime-86400`.
* **And** it gracefully strips any pre-existing `-country-` or `-session-` flags from `Config.PROXY_URL` before appending new ones.

### AC-3: AD-SN-3 Multi-Account 1-to-1 Sticky Session Binding
* **Given** an execution of Facebook or Twitter automation for a specific `account_id`
* **When** resolving the proxy for the account
* **Then** the system checks Redis Hash `xactions:proxy_bindings` for `account_id`
* **And** if not present or expired, builds a SocksNode URL with `session-fb_<account_id>-lifetime-86400` and saves it to Redis.
* **And** every request for that account reuses the exact same sticky session string for 24 hours.

### AC-4: AD-SN-4 Circuit Breaker & Rotate-on-Block
* **Given** a target site (Facebook, Google, Batdongsan) returns HTTP 403, 429, or a Captcha challenge
* **When** the error is intercepted
* **Then** the current `session_id` is placed into `QuarantineState` for 5 minutes
* **And** the provider generates a fresh `session_id` (`fb_<account_id>_rot_<timestamp>`) and retries up to 2 times.

### AC-5: AD-SN-5 Request Routing Interception (Bandwidth Optimization)
* **Given** a Playwright or Puppeteer browser instance launched for text/DOM scraping
* **When** page requests are intercepted
* **Then** requests with resource types `image`, `font`, `media` are aborted (`route.abort()`) unless explicitly overridden by `options.allowMedia === true`.
* **And** total bandwidth per page is reduced by $\ge 70\%$.

### AC-6: AD-SN-6 Anti-Leak & Fingerprint Coherence
* **Given** browser launch options with a SocksNode proxy targeting `-country-vn`
* **When** launching the Chromium instance
* **Then** `--disable-webrtc` is passed to prevent STUN IP leak
* **And** `RTCPeerConnection` is disabled
* **And** Timezone is set to `Asia/Ho_Chi_Minh`, Locale to `vi-VN`, and Geolocation to VN coordinates (`10.8231, 106.6297`).

### AC-7: Comprehensive Unit & Live Test Suite
* **Given** `tests/proxy/socksnode-provider.test.js` and `nowing_backend/tests/unit/utils/proxy/test_socksnode_provider.py`
* **When** running test suites
* **Then** all unit tests pass offline with zero mocks.
* **And** live tests verify exit IP is in Vietnam (VNPT/Viettel) when `RUN_LIVE_PROXY_TESTS=true`.

---

## Technical Guardrails & Implementation Files

| File | Action | Description |
|---|---|---|
| `src/proxy/providers.js` | **UPDATE** | Add `'socksnode'` preset to `PROVIDER_PRESETS` in `DynamicTunnelProvider`. |
| `types/proxy.d.ts` | **UPDATE** | Add `'socksnode'` to `ProviderPreset` union type. |
| `nowing_backend/app/utils/proxy/providers/socksnode.py` | **NEW** | Python `SocksNodeProvider` implementation. |
| `nowing_backend/app/utils/proxy/registry.py` | **UPDATE** | Register `socksnode` provider. |
| `tests/proxy/socksnode-provider.test.js` | **NEW** | Vitest unit tests for SocksNode preset. |
| `nowing_backend/tests/unit/utils/proxy/test_socksnode_provider.py` | **NEW** | Pytest unit tests for Python provider. |

---

## Test Execution Commands

```bash
# Node.js Vitest
npx vitest run tests/proxy/socksnode-provider.test.js

# Python Pytest
pytest nowing_backend/tests/unit/utils/proxy/test_socksnode_provider.py
```
