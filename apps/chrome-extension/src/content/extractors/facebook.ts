/**
 * Facebook Groups & Posts DOM Extractor.
 * Extracts post content, author name, phone numbers, price, and canonical link.
 */

import { LeadClipPayload } from '../../types';
import {
  canonicalizeUrl,
  extractEmails,
  extractPrice,
  extractVietnamesePhones,
} from '../../utils/normalizer';

export function extractFacebookLead(): LeadClipPayload | null {
  const url = window.location.href;
  if (!url.includes('facebook.com')) return null;

  // 1. Post Content
  let postContent = '';
  const postElements = document.querySelectorAll(
    'div[dir="auto"], [data-ad-preview="message"], [data-ad-comet-preview="message"]'
  );
  if (postElements.length > 0) {
    const textBlocks: string[] = [];
    postElements.forEach((el) => {
      const text = el.textContent?.trim();
      if (text && text.length > 15 && !textBlocks.includes(text)) {
        textBlocks.push(text);
      }
    });
    postContent = textBlocks.slice(0, 3).join('\n\n');
  }

  // 2. Author Name
  let authorName: string | null = null;
  const authorCandidates = document.querySelectorAll(
    'h2 strong, h3 strong, a[role="link"] strong, [data-ad-preview="message"] strong'
  );
  for (const el of Array.from(authorCandidates)) {
    const name = el.textContent?.trim();
    if (name && name.length > 2 && name.length < 50) {
      authorName = name;
      break;
    }
  }

  // Fallback to document title if no author found
  if (!authorName) {
    const titleMatch = document.title.replace(/\| Facebook$/i, '').trim();
    if (titleMatch && titleMatch.length > 2) {
      authorName = titleMatch;
    }
  }

  // 3. Phone & Email regex fallback scanner
  const fullText = document.body.innerText || '';
  const phones = extractVietnamesePhones(postContent || fullText);
  const emails = extractEmails(postContent || fullText);
  const detectedPhone = phones.length > 0 ? phones[0] : null;
  const detectedEmail = emails.length > 0 ? emails[0] : null;

  // 4. Price & Location
  const price = extractPrice(postContent || fullText);

  return {
    source_canonical_url: canonicalizeUrl(url),
    source_platform: 'facebook',
    contact_name: authorName,
    phone: detectedPhone,
    email: detectedEmail,
    company_name: authorName,
    post_content: postContent || null,
    price: price,
    metadata: {
      all_phones: phones,
      all_emails: emails,
      page_title: document.title,
    },
  };
}
