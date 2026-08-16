# Nowing Lead Clipper — Chrome Extension (Manifest V3)

1-Click Lead Capturing for Growth Hackers, Sourcers, and Real Estate Brokers directly into your Nowing Workspace.

## Architectural Invariants (INV-24.5)
- **Token Security:** Background Service Worker isolates PAT token storage in `chrome.storage.local`. Content scripts never touch raw tokens and communicate solely via `chrome.runtime.sendMessage`.
- **Deduplication:** SHA-256 deduplication hashing: `SHA256(workspace_id + source_canonical_url + normalized_phone)`.
- **Shadow DOM:** The `⚡ Clip to Nowing` floating action pill is mounted inside an isolated Shadow Root (`#nowing-clipper-host`) to prevent CSS and JS bleed from host platforms.
- **Offline Resilient:** Network failures automatically buffer leads in local offline queue with 1-click batch sync.

## Platforms Supported
- Facebook Groups & Posts (`facebook.com`)
- Batdongsan.com.vn (`batdongsan.com.vn`)
- TopCV (`topcv.vn`)
- LinkedIn / Chợ Tốt / Generic Webpages

## Development & Build

```bash
cd apps/chrome-extension
pnpm install
pnpm build
```

Load unpacked in Chrome:
1. Open `chrome://extensions/`
2. Enable "Developer mode" (top right)
3. Click "Load unpacked" and select `apps/chrome-extension/` or `dist/`.
4. Open the extension popup, enter your Nowing Backend URL, Workspace ID, and PAT token with `leads:clipper:write` scope.
