/**
 * TopCV DOM Extractor.
 * Extracts candidate profile or employer job posting.
 */

import { LeadClipPayload } from '../../types';
import {
  canonicalizeUrl,
  extractEmails,
  extractPrice,
  extractVietnamesePhones,
} from '../../utils/normalizer';

export function extractTopcvLead(): LeadClipPayload | null {
  const url = window.location.href;
  if (!url.includes('topcv.vn')) return null;

  // Candidate Profile or Job Posting Title
  const candidateNameEl = document.querySelector(
    '.candidate-name, .box-candidate h1, .profile-header h1, .name-candidate'
  );
  const jobTitleEl = document.querySelector('.job-detail__info--title, .job-title, h1');

  const name = candidateNameEl?.textContent?.trim();
  const jobTitle = jobTitleEl?.textContent?.trim() || document.title;

  // Company Name
  const companyEl = document.querySelector(
    '.company-name, .job-detail__company--name, .box-company-name a'
  );
  const companyName = companyEl?.textContent?.trim() || null;

  // Location
  const locationEl = document.querySelector(
    '.job-detail__info--location, .candidate-address, .box-address'
  );
  const location = locationEl?.textContent?.trim() || null;

  // Salary / Price
  const salaryEl = document.querySelector(
    '.job-detail__info--salary, .candidate-salary, .box-salary'
  );
  const salary = salaryEl?.textContent?.trim() || null;

  // Content
  const contentEl = document.querySelector(
    '.job-description, .candidate-detail, .box-candidate-detail, .job-detail__body'
  );
  const content = contentEl?.textContent?.trim() || '';

  const fullText = document.body.innerText || '';
  const phones = extractVietnamesePhones(content || fullText);
  const emails = extractEmails(content || fullText);

  return {
    source_canonical_url: canonicalizeUrl(url),
    source_platform: 'topcv',
    contact_name: name || companyName || 'Ứng viên / Nhà tuyển dụng',
    phone: phones.length > 0 ? phones[0] : null,
    email: emails.length > 0 ? emails[0] : null,
    company_name: companyName || name || 'TopCV Lead',
    post_content: content || jobTitle,
    price: salary || extractPrice(content || fullText),
    location: location,
    metadata: {
      job_title: jobTitle,
      extracted_at: new Date().toISOString(),
    },
  };
}
