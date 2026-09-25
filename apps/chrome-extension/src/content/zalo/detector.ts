/**
 * Zalo active-conversation phone detection (Story 37.4 / AC-1).
 *
 * Zalo web uses obfuscated class names, so detection is semantic-only
 * (AD-118): URL params, `zalo.me/{phone}` assisted links, header-ish
 * regions, then a whole-body fallback scan for Vietnamese mobile numbers.
 */

import { extractVietnamesePhones } from '../../utils/normalizer';

// Selectors ordered by likelihood of containing the *active* conversation's
// identity. Semantic attributes first per AD-118; class fragments are a
// last-resort heuristic, never the sole mechanism.
const HEADER_CANDIDATE_SELECTORS = [
  '[class*="chat-header"]',
  '[class*="chatHeader"]',
  '[class*="header"] [class*="title"]',
  '[class*="conversation"] [class*="name"]',
  'header',
];

function extractPhone(text: string | null | undefined): string | null {
  if (!text) return null;
  const phones = extractVietnamesePhones(text);
  return phones.length > 0 ? phones[0] : null;
}

function phoneFromZaloLink(href: string | null): string | null {
  // Assisted links look like https://zalo.me/0912345678. Parse the URL so
  // `notzalo.me/0912…` or `zalo.me.evil.com/…` can't spoof a match.
  if (!href) return null;
  try {
    const url = new URL(href.trim());
    const host = url.hostname.toLowerCase();
    if (host !== 'zalo.me' && !host.endsWith('.zalo.me')) return null;
    return extractPhone(url.pathname.slice(1));
  } catch {
    return null;
  }
}

/**
 * Best-effort phone of the currently open conversation. Returns null when no
 * plausible Vietnamese mobile is visible — deliberately no whole-body scan:
 * a stray number in the sidebar or a quoted message would be attributed to
 * the wrong conversation (and drive a wrong DNC decision).
 */
export function detectActiveZaloPhone(): string | null {
  // 1. URL itself (assisted-link redirects can keep the number in the path).
  const fromUrl =
    extractPhone(window.location.pathname) ||
    extractPhone(window.location.search);
  if (fromUrl) return fromUrl;

  // 2. zalo.me/{phone} links inside the open conversation/profile card.
  // Real Zalo Web renders chat links either as `<a class="text-is-link">`
  // with no href (URL lives in the anchor text) or as plain text inside
  // the message bubble — so scan anchors first, then leaf text nodes.
  for (const anchor of Array.from(document.querySelectorAll('a'))) {
    const phone =
      phoneFromZaloLink(anchor.getAttribute('href')) ||
      phoneFromZaloLink(anchor.textContent);
    if (phone) return phone;
  }
  const linkTexts = document.evaluate(
    "//*[contains(text(), 'zalo.me/')]",
    document,
    null,
    XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
    null
  );
  for (let i = 0; i < linkTexts.snapshotLength; i++) {
    const phone = phoneFromZaloLink(
      (linkTexts.snapshotItem(i) as HTMLElement).textContent
    );
    if (phone) return phone;
  }

  // 3. Header-ish regions: text content + title/aria attributes.
  for (const selector of HEADER_CANDIDATE_SELECTORS) {
    for (const el of Array.from(document.querySelectorAll(selector))) {
      const phone =
        extractPhone(el.textContent) ||
        extractPhone(el.getAttribute('title')) ||
        extractPhone(el.getAttribute('aria-label'));
      if (phone) return phone;
    }
  }

  return null;
}
