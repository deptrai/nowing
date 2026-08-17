/**
 * Generic fallback extractor for unknown platforms.
 * ponytail: intentionally conservative — only surfaces obvious PII signals
 * already visible on the page, leaving platform-specific enrichment to
 * dedicated extractors.
 */

import { LeadClipPayload } from '../../types';
import { canonicalizeUrl, extractEmails, extractPrice, extractVietnamesePhones } from '../../utils/normalizer';

export function extractGenericLead(): LeadClipPayload | null {
  const bodyText = document.body?.innerText || '';
  const phones = extractVietnamesePhones(bodyText);
  const emails = extractEmails(bodyText);
  const price = extractPrice(bodyText);

  if (phones.length === 0 && emails.length === 0) {
    return null;
  }

  return {
    source_canonical_url: canonicalizeUrl(window.location.href),
    source_platform: 'generic',
    phone: phones[0] || null,
    email: emails[0] || null,
    price: price,
    post_content: bodyText.slice(0, 500),
    metadata: {
      phones,
      emails,
    },
  };
}
