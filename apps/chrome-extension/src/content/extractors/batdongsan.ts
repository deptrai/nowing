/**
 * Batdongsan.com.vn DOM Extractor.
 * Extracts listing title, price, area, address, author contact, and phone.
 */

import { LeadClipPayload } from '../../types';
import {
  canonicalizeUrl,
  extractEmails,
  extractPrice,
  extractVietnamesePhones,
  normalizeVietnamesePhone,
} from '../../utils/normalizer';

export function extractBatdongsanLead(): LeadClipPayload | null {
  const url = window.location.href;
  if (!url.includes('batdongsan.com.vn')) return null;

  // 1. Listing Title
  const titleEl = document.querySelector('h1.re__pr-title, .js__pr-title, h1');
  const title = titleEl?.textContent?.trim() || document.title;

  // 2. Price & Specs
  let price: string | null = null;
  const priceEl = document.querySelector(
    '.re__pr-specs-content-item-title, .re__short-info-item .value, [param="price"]'
  );
  if (priceEl?.textContent) {
    price = priceEl.textContent.trim();
  }

  // 3. Location / Address
  let location: string | null = null;
  const addressEl = document.querySelector(
    '.re__pr-address, .js__pr-address, .re__section-body .re__pr-address'
  );
  if (addressEl?.textContent) {
    location = addressEl.textContent.trim();
  }

  // 4. Contact Name & Phone
  let contactName: string | null = null;
  const contactNameEl = document.querySelector(
    '.re__contact-name, .js__contact-name, .re__author-name, .re__contact-box .name'
  );
  if (contactNameEl?.textContent) {
    contactName = contactNameEl.textContent.trim();
  }

  let phone: string | null = null;
  // Check explicit phone button or data attribute
  const phoneEl = document.querySelector(
    '[data-phone], [data-mobile], .phoneEvent, .js__phone-event, .re__btn-call'
  );
  if (phoneEl) {
    const rawPhone =
      phoneEl.getAttribute('data-phone') ||
      phoneEl.getAttribute('data-mobile') ||
      phoneEl.textContent;
    if (rawPhone) {
      phone = normalizeVietnamesePhone(rawPhone);
    }
  }

  // 5. Description Content
  const descEl = document.querySelector(
    '.re__pr-description, .re__section-body.re__pr-description, .js__pr-description'
  );
  const description = descEl?.textContent?.trim() || '';

  // Fallback scanner if phone not found in explicit selector
  const fullText = document.body.innerText || '';
  if (!phone) {
    const phones = extractVietnamesePhones(description || fullText);
    if (phones.length > 0) phone = phones[0];
  }

  const emails = extractEmails(description || fullText);
  const detectedEmail = emails.length > 0 ? emails[0] : null;

  if (!price) {
    price = extractPrice(description || title || fullText);
  }

  return {
    source_canonical_url: canonicalizeUrl(url),
    source_platform: 'batdongsan',
    contact_name: contactName || 'Môi giới / Chủ nhà',
    phone: phone,
    email: detectedEmail,
    company_name: contactName || 'Bất động sản',
    post_content: description || title,
    price: price,
    location: location,
    metadata: {
      listing_title: title,
      extracted_at: new Date().toISOString(),
    },
  };
}
