/**
 * Text & URL normalization utilities for Lead Clipper.
 * Aligned with backend INV-24.5 contract.
 */

export function normalizeVietnamesePhone(phone: string | null | undefined): string {
  if (!phone) return '';
  let digits = phone.replace(/\D/g, '');
  if (digits.startsWith('84') && digits.length >= 10) {
    // +8409... / 8409... → drop the 84 prefix and any leading 0 left over
    digits = '0' + digits.slice(2).replace(/^0+/, '');
  } else if (!digits.startsWith('0') && digits.length === 9) {
    // bare 9-digit mobile number, e.g. 912345678
    digits = '0' + digits;
  }
  return digits;
}

export function extractVietnamesePhones(text: string): string[] {
  if (!text) return [];
  // Vietnamese mobile phone regex: 03x, 05x, 07x, 08x, 09x or +84/84 with optional leading 0.
  const phonePattern = /(?:\+84(?:0)?|84(?:0)?|0)(?:3[2-9]|5[25689]|7[06-9]|8[1-9]|9[0-9])\d{7}/g;
  // Remove whitespace and visual separators before matching so formatted numbers resolve correctly.
  const clean = text.replace(/[\s\.\-\(\)]/g, '');
  const matches = clean.match(phonePattern) || [];
  return Array.from(new Set(matches.map(p => normalizeVietnamesePhone(p))));
}

export function extractEmails(text: string): string[] {
  if (!text) return [];
  const emailPattern = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
  const matches = text.match(emailPattern) || [];
  return Array.from(new Set(matches.map(e => e.toLowerCase())));
}

export function extractPrice(text: string): string | null {
  if (!text) return null;
  // Match Vietnamese real estate / salary price patterns (e.g. 5 tỷ, 15 triệu, 2.5 tỷ, $1000)
  const pricePattern = /(\d+(?:[\.,]\d+)?\s*(?:tỷ|triệu|tr|nghìn|k|usd|\$|vnd|đ|man|củ))/i;
  const match = text.match(pricePattern);
  return match ? match[0].trim() : null;
}

function ensureScheme(url: string): string {
  const clean = url.trim();
  if (clean.startsWith('http://') || clean.startsWith('https://')) {
    return clean;
  }
  return `https://${clean}`;
}

const TRACKING_PARAMS = new Set([
  'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
  'fbclid', 'gclid', 'ref', 'source', '_ga', '_gl', 'gad_source',
  'gbraid', 'wbraid', 'igshid', 'fb_action_ids', 'fb_action_types',
  'mc_cid', 'mc_eid',
]);

export function canonicalizeUrl(url: string): string {
  if (!url) return '';
  try {
    const parsed = new URL(ensureScheme(url));

    // Keep non-tracking query params, preserve original key casing.
    const searchParams = new URLSearchParams();
    parsed.searchParams.forEach((value, key) => {
      if (!TRACKING_PARAMS.has(key.toLowerCase()) && !key.toLowerCase().startsWith('utm_')) {
        searchParams.append(key, value);
      }
    });

    // Strip one or more trailing slashes from non-root paths.
    const cleanPath =
      parsed.pathname.length > 1 ? parsed.pathname.replace(/\/+$/, '') : parsed.pathname;

    const queryString = searchParams.toString();
    return `${parsed.protocol}//${parsed.host.toLowerCase()}${cleanPath}${queryString ? '?' + queryString : ''}`;
  } catch {
    // Fallback: just strip the query string.
    return url.split('?')[0] || url;
  }
}
