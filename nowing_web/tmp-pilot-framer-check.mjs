import { chromium } from 'playwright-core';

const browser = await chromium.launch({ headless: false });
const context = await browser.newContext();
const page = await context.newPage();

const warnings = [];
page.on('console', msg => {
  const text = msg.text();
  if (msg.type() === 'warning' && /opacity|motion|framer|undefined/.test(text)) {
    warnings.push({ type: msg.type(), text, url: msg.location().url });
    console.log(`[${msg.type()}] ${text}`);
  }
});

page.on('pageerror', err => {
  console.log('[pageerror]', err.message);
});

const baseURL = 'http://localhost:3000';

await page.goto(baseURL, { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);

console.log('Warnings captured:', JSON.stringify(warnings, null, 2));
await browser.close();
