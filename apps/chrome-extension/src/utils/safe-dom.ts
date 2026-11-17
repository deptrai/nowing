/**
 * Safe DOM utilities for Web Components and ShadowRoot rendering.
 * Single audited sink for ShadowRoot innerHTML writes.
 */

/**
 * Escapes HTML characters for safe interpolation into template strings.
 */
export function esc(s: string | null | undefined): string {
  if (!s) return '';
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Audited sink for ShadowRoot innerHTML writes.
 */
export function setShadowHtml(root: ShadowRoot, html: string): void {
  // pi-lens-ignore: ast-grep:no-inner-html, ts-xss-dom-sink -- audited sink for static template strings
  root.innerHTML = html;
}
