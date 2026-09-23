/**
 * Zalo message input insertion (Story 37.4 / AC-3 / AD-118).
 *
 * Zero-ban guarantee: we only *fill* the composer via semantic selectors and
 * standard InputEvent/insertText mechanics. The human always clicks Send —
 * nothing here ever dispatches keystrokes for Enter or clicks the send button.
 */

// Real Zalo Web keeps the composer as `div#richInput` with
// contenteditable="false" until it is focused — it flips to "true" on
// focus. Include it explicitly so the composer is found even before focus.
const ZALO_INPUT_SELECTOR =
  'div[contenteditable="true"], div[role="textbox"], div#richInput';

export function findZaloInput(): HTMLElement | null {
  // Prefer the composer closest to the bottom of the viewport — the reply
  // box — over any other contenteditable (e.g. search fields).
  const candidates = Array.from(
    document.querySelectorAll<HTMLElement>(ZALO_INPUT_SELECTOR)
    // getClientRects covers position:fixed composers, whose offsetParent is
    // null even when visible.
  ).filter((el) => el.getClientRects().length > 0);

  if (candidates.length === 0) return null;
  return candidates.reduce((a, b) =>
    a.getBoundingClientRect().top > b.getBoundingClientRect().top ? a : b
  );
}

export function getZaloInputDraft(input: HTMLElement): string {
  return (input.innerText || '').trim();
}

function moveCaretToEnd(el: HTMLElement) {
  const sel = window.getSelection();
  const range = document.createRange();
  range.selectNodeContents(el);
  range.collapse(false);
  sel?.removeAllRanges();
  sel?.addRange(range);
}

function dispatchInsertFallback(el: HTMLElement, text: string) {
  // Some editors ignore execCommand; fire a standard InputEvent and mutate
  // the DOM directly so the composer state stays consistent.
  el.dispatchEvent(
    new InputEvent('beforeinput', {
      inputType: 'insertText',
      data: text,
      bubbles: true,
      cancelable: true,
      composed: true,
    })
  );
  el.innerText = text;
  el.dispatchEvent(
    new InputEvent('input', {
      inputType: 'insertText',
      data: text,
      bubbles: true,
      composed: true,
    })
  );
}

/**
 * Insert `text` into the active Zalo composer.
 * mode='overwrite' replaces any existing draft; mode='append' adds the text
 * on a new line below the draft (AC-5).
 */
export function insertIntoZaloComposer(
  text: string,
  mode: 'overwrite' | 'append'
): boolean {
  const input = findZaloInput();
  if (!input) return false;

  input.focus();

  let payload = text;
  if (mode === 'overwrite') {
    // selectAll within the focused contenteditable, then insertText replaces.
    document.execCommand('selectAll', false);
  } else {
    moveCaretToEnd(input);
    const existing = getZaloInputDraft(input);
    if (existing) payload = `\n${text}`;
  }

  const ok = document.execCommand('insertText', false, payload);
  if (!ok) {
    const draft = mode === 'append' ? getZaloInputDraft(input) : '';
    dispatchInsertFallback(input, draft ? `${draft}\n${text}` : text);
  }
  return true;
}
