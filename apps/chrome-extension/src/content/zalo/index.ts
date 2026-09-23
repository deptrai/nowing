/**
 * Zalo Co-pilot orchestrator (Story 37.4 / AC-1).
 * Watches the SPA for conversation changes, re-detects the active phone and
 * feeds it to the overlay. Pill only renders while a phone is detected.
 */

import { detectActiveZaloPhone } from './detector';
import { ZaloCopilotOverlay } from './overlay';

let overlay: ZaloCopilotOverlay | null = null;
let observer: MutationObserver | null = null;
let debounce: ReturnType<typeof setTimeout> | null = null;

function refresh() {
  // No local dedup — setPhone() already dedups on `phone === this.phone`
  // and deliberately refetches when a previous lookup errored.
  overlay?.setPhone(detectActiveZaloPhone());
}

export function initZaloCopilot() {
  if (overlay) return;
  overlay = new ZaloCopilotOverlay();

  refresh();

  // Zalo is a SPA — conversation switches mutate the DOM without navigation.
  observer = new MutationObserver(() => {
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(refresh, 800);
  });
  observer.observe(document.body, { childList: true, subtree: true });
}
