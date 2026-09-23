/**
 * Zalo Co-pilot overlay (Story 37.4 / AC-1 to AC-5 / AD-118).
 *
 * Shadow-DOM isolated UI (same pattern as FloatingActionPill): a 36px pill at
 * the right edge expands into a 320px contextual drawer. All prospect data is
 * rendered through `esc()` — it comes from the DB and must never be trusted.
 */

import type { ZaloCopilotContext } from '../../types';
import {
  findZaloInput,
  getZaloInputDraft,
  insertIntoZaloComposer,
} from './insert';

type PitchTab = 'short' | 'link';

function esc(value: string | null | undefined): string {
  const div = document.createElement('div');
  div.textContent = value ?? '';
  return div.innerHTML;
}

export class ZaloCopilotOverlay {
  private host: HTMLElement | null = null;
  private shadow: ShadowRoot | null = null;
  private context: ZaloCopilotContext | null = null;
  private phone: string | null = null;
  private expanded = false;
  private activeTab: PitchTab = 'short';
  private loading = false;
  private error: string | null = null;
  private draftConflict = false;
  private requestSeq = 0;

  constructor() {
    this.init();
  }

  private init() {
    if (document.getElementById('nowing-zalo-copilot-host')) return;
    this.host = document.createElement('div');
    this.host.id = 'nowing-zalo-copilot-host';
    this.host.style.cssText =
      'position:fixed;top:50%;right:0;z-index:2147483647;' +
      'transform:translateY(-50%);' +
      'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;';
    this.shadow = this.host.attachShadow({ mode: 'open' });
    document.body.appendChild(this.host);
  }

  /** Called by the detector loop whenever the active phone may have changed. */
  public async setPhone(phone: string | null) {
    if (phone === this.phone && !this.error) return;
    this.phone = phone;
    this.context = null;
    this.error = null;
    this.draftConflict = false;
    // Invalidate any in-flight request before any early return, then discard
    // out-of-order responses: a slow fetch for phone A must never overwrite
    // the context of the now-active phone B (or a no-phone state).
    const seq = ++this.requestSeq;

    if (!phone) {
      this.loading = false;
      this.render();
      return;
    }

    this.loading = true;
    this.render();
    try {
      const res: any = await chrome.runtime.sendMessage({
        action: 'GET_ZALO_CONTEXT',
        phone,
      });
      if (seq !== this.requestSeq) return; // stale response
      if (res?.success && res.context) {
        this.context = res.context as ZaloCopilotContext;
      } else {
        this.error = res?.message || 'Không tải được context';
      }
    } catch (err: any) {
      if (seq !== this.requestSeq) return;
      this.error = err?.message || 'Mất kết nối background worker';
    } finally {
      if (seq === this.requestSeq) {
        this.loading = false;
        this.render();
      }
    }
  }

  public destroy() {
    this.host?.remove();
    this.host = null;
    this.shadow = null;
  }

  private currentPitch(): string {
    if (!this.context) return '';
    return this.activeTab === 'link'
      ? this.context.pitch_with_link || this.context.pitch_short || ''
      : this.context.pitch_short || '';
  }

  private handleInsert(mode: 'overwrite' | 'append') {
    const text = this.currentPitch();
    if (!text || this.context?.dnc_blocked) return;
    const ok = insertIntoZaloComposer(text, mode);
    this.draftConflict = false;
    // Render first — the innerHTML reset would destroy a toast appended
    // before it ever painted.
    this.render();
    this.showToast(
      ok
        ? '✓ Đã chèn vào ô soạn tin — bạn tự bấm Gửi nhé'
        : '✗ Không tìm thấy ô nhập tin nhắn Zalo',
      ok ? 'success' : 'error'
    );
  }

  private handleInsertClick() {
    // AC-5: non-destructive paste — prompt when a draft already exists.
    const input = findZaloInput();
    if (input && getZaloInputDraft(input)) {
      this.draftConflict = true;
      this.render();
      return;
    }
    this.handleInsert('overwrite');
  }

  private showToast(message: string, type: 'success' | 'error') {
    if (!this.shadow) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    this.shadow.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  // ---------------------------------------------------------------- render

  private render() {
    if (!this.shadow) return;
    // Phone lost while drawer open → collapse instead of showing a blank
    // "Số  chưa khớp lead" message.
    if (!this.phone) this.expanded = false;

    this.shadow.innerHTML = `
      <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        .pill {
          width: 36px; height: 36px; border-radius: 9999px 0 0 9999px;
          background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
          color: #fff; border: none; cursor: pointer; font-size: 17px;
          display: flex; align-items: center; justify-content: center;
          box-shadow: -4px 4px 16px rgba(0,0,0,0.35);
          transition: transform 0.15s ease;
        }
        .pill:hover { transform: translateX(-2px); }
        .pill.has-match { background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%); }
        .drawer {
          width: 320px; max-height: 82vh; overflow-y: auto;
          background: rgba(15, 23, 42, 0.97); backdrop-filter: blur(14px);
          border: 1px solid rgba(255,255,255,0.14); border-right: none;
          border-radius: 14px 0 0 14px; color: #f1f5f9;
          box-shadow: -12px 0 32px rgba(0,0,0,0.45);
          padding: 14px; font-size: 12px; line-height: 1.5;
        }
        .drawer-header {
          display: flex; align-items: center; justify-content: space-between;
          margin-bottom: 10px;
        }
        .drawer-title { font-size: 13px; font-weight: 700; color: #a5b4fc; }
        .btn-close {
          background: none; border: none; color: #94a3b8; font-size: 16px;
          cursor: pointer; padding: 2px 6px; border-radius: 6px;
        }
        .btn-close:hover { background: rgba(255,255,255,0.1); color: #fff; }
        .banner-dnc {
          background: rgba(220, 38, 38, 0.18); border: 1px solid #dc2626;
          color: #fca5a5; border-radius: 8px; padding: 8px 10px;
          font-weight: 600; margin-bottom: 10px;
        }
        .section { margin-bottom: 10px; }
        .section-label {
          font-size: 10px; font-weight: 700; text-transform: uppercase;
          letter-spacing: 0.6px; color: #64748b; margin-bottom: 4px;
        }
        .lead-name { font-size: 14px; font-weight: 700; color: #fff; }
        .lead-meta { color: #94a3b8; margin-top: 2px; }
        .chip {
          display: inline-block; background: rgba(99,102,241,0.2);
          color: #a5b4fc; border-radius: 6px; padding: 1px 7px;
          font-size: 10px; font-weight: 600; margin-right: 4px;
        }
        .signal {
          background: rgba(255,255,255,0.05); border-radius: 6px;
          padding: 6px 8px; margin-bottom: 4px;
        }
        .signal-type { color: #34d399; font-weight: 600; }
        .signal-date { color: #64748b; font-size: 10px; }
        .tabs { display: flex; gap: 6px; margin-bottom: 6px; }
        .tab {
          flex: 1; text-align: center; padding: 6px 0; border-radius: 8px;
          border: 1px solid rgba(255,255,255,0.12); cursor: pointer;
          background: transparent; color: #94a3b8; font-size: 12px;
          font-weight: 600;
        }
        .tab.active {
          background: rgba(99,102,241,0.25); border-color: #6366f1;
          color: #e0e7ff;
        }
        .pitch-preview {
          background: rgba(255,255,255,0.06); border-radius: 8px;
          padding: 10px; white-space: pre-wrap; word-break: break-word;
          max-height: 180px; overflow-y: auto; color: #e2e8f0;
          margin-bottom: 10px;
        }
        .btn-insert {
          width: 100%; padding: 10px; border: none; border-radius: 10px;
          background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
          color: #fff; font-size: 13px; font-weight: 700; cursor: pointer;
        }
        .btn-insert:hover:not(:disabled) { filter: brightness(1.12); }
        .btn-insert:disabled { opacity: 0.45; cursor: not-allowed; }
        .conflict-bar {
          background: rgba(217, 119, 6, 0.15); border: 1px solid #d97706;
          border-radius: 8px; padding: 8px; margin-bottom: 8px;
        }
        .conflict-bar p { color: #fcd34d; margin-bottom: 6px; }
        .conflict-actions { display: flex; gap: 6px; }
        .btn-mini {
          flex: 1; padding: 5px 0; border-radius: 6px; font-size: 11px;
          font-weight: 600; cursor: pointer; border: 1px solid rgba(255,255,255,0.2);
          background: rgba(255,255,255,0.08); color: #e2e8f0;
        }
        .btn-mini:hover { background: rgba(255,255,255,0.16); }
        .state-msg { color: #94a3b8; text-align: center; padding: 18px 0; }
        .toast {
          position: fixed; bottom: 24px; right: 24px; padding: 8px 14px;
          border-radius: 8px; font-size: 12px; font-weight: 500; color: #fff;
          opacity: 0; transform: translateY(10px);
          transition: all 0.25s ease-out; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
          z-index: 2147483647;
        }
        .toast.show { opacity: 1; transform: translateY(0); }
        .toast-success { background: #059669; }
        .toast-error { background: #dc2626; }
      </style>
      ${this.expanded ? this.renderDrawer() : this.renderPill()}
    `;

    this.bindEvents();
  }

  private renderPill(): string {
    // AC-1: the pill only exists while a conversation phone is detected.
    if (!this.phone) return '';
    const hasMatch = !!this.context?.matched;
    return `<button class="pill ${hasMatch ? 'has-match' : ''}" id="copilot-pill"
      title="Nowing Co-pilot">⚡</button>`;
  }

  private renderDrawer(): string {
    if (this.loading) {
      return `<div class="drawer">
        ${this.drawerHeader()}
        <div class="state-msg">Đang tải context từ Nowing…</div>
      </div>`;
    }
    if (this.error) {
      return `<div class="drawer">
        ${this.drawerHeader()}
        <div class="state-msg">⚠ ${esc(this.error)}</div>
      </div>`;
    }
    const ctx = this.context;
    if (!ctx || !ctx.matched || !ctx.lead) {
      const dncNote = ctx?.dnc_blocked
        ? this.renderDncBanner(ctx.dnc_reason)
        : '';
      return `<div class="drawer">
        ${this.drawerHeader()}
        ${dncNote}
        <div class="state-msg">Số ${esc(this.phone)} chưa khớp lead đã unlock trong workspace.</div>
      </div>`;
    }

    const lead = ctx.lead;
    const metaBits = [lead.industry, lead.location].filter(Boolean).join(' • ');
    const signals = ctx.signals
      .map(
        (s) => `<div class="signal">
          <span class="signal-type">${esc(s.signal_type)}</span>
          <span class="signal-date"> · ${Math.round(s.confidence)}% · ${esc(
            (s.detected_at || '').slice(0, 10)
          )}</span>
        </div>`
      )
      .join('');

    return `<div class="drawer">
      ${this.drawerHeader()}
      ${ctx.dnc_blocked ? this.renderDncBanner(ctx.dnc_reason) : ''}

      <div class="section">
        <div class="lead-name">${esc(lead.company_name)}</div>
        <div class="lead-meta">
          ${lead.contact_name ? `👤 ${esc(lead.contact_name)}` : ''}
          ${lead.contact_title ? ` — ${esc(lead.contact_title)}` : ''}
        </div>
        <div class="lead-meta">${esc(metaBits)}</div>
        <div style="margin-top:6px">
          <span class="chip">${esc(lead.status)}</span>
          ${
            lead.intent_score != null
              ? `<span class="chip">intent ${Math.round(lead.intent_score * 100)}%</span>`
              : ''
          }
        </div>
      </div>

      ${
        signals
          ? `<div class="section">
              <div class="section-label">Tín hiệu gần đây</div>
              ${signals}
            </div>`
          : ''
      }

      <div class="section">
        <div class="section-label">Pitch gợi ý</div>
        <div class="tabs">
          <button class="tab ${this.activeTab === 'short' ? 'active' : ''}"
            data-tab="short">Ngắn gọn</button>
          <button class="tab ${this.activeTab === 'link' ? 'active' : ''}"
            data-tab="link">Kèm link Pitch</button>
        </div>
        <div class="pitch-preview">${esc(this.currentPitch())}</div>
      </div>

      ${
        this.draftConflict
          ? `<div class="conflict-bar">
              <p>Ô nhập đang có nội dung nháp.</p>
              <div class="conflict-actions">
                <button class="btn-mini" data-mode="overwrite">Ghi đè</button>
                <button class="btn-mini" data-mode="append">Nối tiếp bên dưới</button>
                <button class="btn-mini" data-mode="cancel">Huỷ</button>
              </div>
            </div>`
          : ''
      }

      <button class="btn-insert" id="btn-insert"
        ${ctx.dnc_blocked || !this.currentPitch() ? 'disabled' : ''}>
        Chèn tin nhắn
      </button>
    </div>`;
  }

  private drawerHeader(): string {
    return `<div class="drawer-header">
      <span class="drawer-title">⚡ Nowing Co-pilot</span>
      <button class="btn-close" id="copilot-close" title="Thu gọn">✕</button>
    </div>`;
  }

  private renderDncBanner(reason: string | null): string {
    return `<div class="banner-dnc">
      ⛔ DNC — số này nằm trong blacklist (Nghị định 91/2020/NĐ-CP).
      ${reason ? `<br/><small>${esc(reason)}</small>` : ''}
      <br/><small>Không được phép chèn/gửi tin nhắn marketing.</small>
    </div>`;
  }

  private bindEvents() {
    if (!this.shadow) return;

    this.shadow.getElementById('copilot-pill')?.addEventListener('click', () => {
      this.expanded = true;
      this.render();
    });
    this.shadow.getElementById('copilot-close')?.addEventListener('click', () => {
      this.expanded = false;
      this.draftConflict = false;
      this.render();
    });
    this.shadow.getElementById('btn-insert')?.addEventListener('click', () =>
      this.handleInsertClick()
    );

    this.shadow.querySelectorAll('.tab').forEach((tab) => {
      tab.addEventListener('click', () => {
        this.activeTab = (tab as HTMLElement).dataset.tab as PitchTab;
        this.draftConflict = false;
        this.render();
      });
    });

    this.shadow.querySelectorAll('.btn-mini').forEach((btn) => {
      btn.addEventListener('click', () => {
        const mode = (btn as HTMLElement).dataset.mode;
        if (mode === 'cancel') {
          this.draftConflict = false;
          this.render();
        } else {
          this.handleInsert(mode as 'overwrite' | 'append');
        }
      });
    });
  }
}
