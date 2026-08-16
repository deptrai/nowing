/**
 * Content Script entry point for Nowing Lead Clipper (Story 24.4).
 * Scans page context, detects leads, and attaches the floating action pill.
 */

import { extractBatdongsanLead } from './extractors/batdongsan';
import { extractFacebookLead } from './extractors/facebook';
import { extractGenericLead } from './extractors/generic';
import { extractTopcvLead } from './extractors/topcv';
import { FloatingActionPill } from './floating_pill';
import { LeadClipPayload } from '../types';

let pill: FloatingActionPill | null = null;

function detectLeadOnPage(): LeadClipPayload | null {
  const host = window.location.hostname.toLowerCase();

  if (host.includes('facebook.com')) {
    return extractFacebookLead() || extractGenericLead();
  }
  if (host.includes('batdongsan.com.vn')) {
    return extractBatdongsanLead() || extractGenericLead();
  }
  if (host.includes('topcv.vn')) {
    return extractTopcvLead() || extractGenericLead();
  }

  // Fallback scanner
  return extractGenericLead();
}

function initClipper() {
  if (!pill) {
    pill = new FloatingActionPill();
  }

  const payload = detectLeadOnPage();
  pill.setLeadPayload(payload);

  // Inform background script of detected lead
  if (payload) {
    chrome.runtime.sendMessage({
      action: 'DETECTED_LEAD_INFO',
      payload,
    }).catch(() => {
      // Background worker might be sleeping; non-critical
    });
  }
}

// Initialize on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => initClipper());
} else {
  initClipper();
}

// Observer for dynamic Single Page Applications (Facebook, TopCV)
let mutationTimeout: any = null;
const observer = new MutationObserver(() => {
  clearTimeout(mutationTimeout);
  mutationTimeout = setTimeout(() => {
    initClipper();
  }, 1000);
});

observer.observe(document.body, {
  childList: true,
  subtree: true,
});
