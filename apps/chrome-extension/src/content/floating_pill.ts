/**
 * Isolated Shadow DOM Floating Action Pill (INV-24.5 / AC-3).
 * Renders an isolated UI component into the host DOM without style collision.
 */

import { LeadClipPayload, LeadClipResponse } from '../types';

export class FloatingActionPill {
  private host: HTMLElement | null = null;
  private shadow: ShadowRoot | null = null;
  private payload: LeadClipPayload | null = null;
  private isDebouncing: boolean = false;
  private isMinimized: boolean = false;

  constructor() {
    this.init();
  }

  public setLeadPayload(payload: LeadClipPayload | null) {
    this.payload = payload;
    this.render();
  }

  private init() {
    if (document.getElementById('nowing-clipper-host')) return;

    this.host = document.createElement('div');
    this.host.id = 'nowing-clipper-host';
    this.host.style.cssText = `
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 2147483647;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    `;
    this.shadow = this.host.attachShadow({ mode: 'open' });
    document.body.appendChild(this.host);
  }

  private async handleClip() {
    if (this.isDebouncing || !this.payload) return;
    this.isDebouncing = true;
    this.render();

    try {
      const response: any = await new Promise((resolve) => {
        chrome.runtime.sendMessage(
          {
            action: 'CLIP_LEAD',
            payload: this.payload,
          },
          (res) => resolve(res)
        );
      });

      if (response?.success) {
        if (response.is_duplicate) {
          this.showToast('ℹ Lead already clipped (Deduplicated)', 'info');
        } else {
          this.showToast('⚡ Lead clipped to Nowing!', 'success');
        }
      } else if (response?.queued) {
        this.showToast('💾 Saved to Offline Queue', 'warning');
      } else {
        this.showToast(`✗ Failed: ${response?.message || 'Check PAT token'}`, 'error');
      }
    } catch (err: any) {
      this.showToast(`✗ Error: ${err?.message || 'Connection failed'}`, 'error');
    } finally {
      // 2s debounce window
      setTimeout(() => {
        this.isDebouncing = false;
        this.render();
      }, 2000);
    }
  }

  private showToast(message: string, type: 'success' | 'info' | 'warning' | 'error') {
    if (!this.shadow) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    this.shadow.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('show');
    }, 10);

    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  private render() {
    if (!this.shadow) return;

    const platformLabel = (this.payload?.source_platform || 'web').toUpperCase();
    const phone = this.payload?.phone;
    const price = this.payload?.price;

    this.shadow.innerHTML = `
      <style>
        * {
          box-sizing: border-box;
          margin: 0;
          padding: 0;
        }
        .pill-container {
          display: flex;
          align-items: center;
          background: rgba(15, 23, 42, 0.95);
          backdrop-filter: blur(12px);
          border: 1px solid rgba(255, 255, 255, 0.15);
          border-radius: 9999px;
          padding: 6px 12px;
          box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
          transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
          color: #f8fafc;
          gap: 8px;
          user-select: none;
        }
        .pill-container:hover {
          border-color: rgba(99, 102, 241, 0.5);
          box-shadow: 0 12px 30px -5px rgba(99, 102, 241, 0.3);
          transform: translateY(-2px);
        }
        .btn-clip {
          display: flex;
          align-items: center;
          gap: 6px;
          background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
          color: #ffffff;
          border: none;
          padding: 8px 14px;
          border-radius: 9999px;
          font-weight: 600;
          font-size: 13px;
          cursor: pointer;
          transition: all 0.2s;
          outline: none;
        }
        .btn-clip:hover:not(:disabled) {
          background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
          filter: brightness(1.1);
        }
        .btn-clip:disabled {
          opacity: 0.7;
          cursor: not-allowed;
        }
        .tag-platform {
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          background: rgba(255, 255, 255, 0.1);
          padding: 2px 6px;
          border-radius: 6px;
          color: #94a3b8;
          letter-spacing: 0.5px;
        }
        .info-preview {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          color: #cbd5e1;
        }
        .phone-chip {
          background: rgba(16, 185, 129, 0.2);
          color: #34d399;
          padding: 2px 6px;
          border-radius: 4px;
          font-weight: 500;
          font-size: 11px;
        }
        .spinner {
          width: 14px;
          height: 14px;
          border: 2px solid rgba(255, 255, 255, 0.3);
          border-top-color: #ffffff;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        .toast {
          position: absolute;
          bottom: 50px;
          right: 0;
          padding: 8px 14px;
          border-radius: 8px;
          font-size: 12px;
          font-weight: 500;
          color: white;
          opacity: 0;
          transform: translateY(10px);
          transition: all 0.25s ease-out;
          white-space: nowrap;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        .toast.show {
          opacity: 1;
          transform: translateY(0);
        }
        .toast-success { background: #059669; }
        .toast-info { background: #0284c7; }
        .toast-warning { background: #d97706; }
        .toast-error { background: #dc2626; }
      </style>

      <div class="pill-container">
        <span class="tag-platform">${platformLabel}</span>
        
        <div class="info-preview">
          ${phone ? `<span class="phone-chip">📞 ${phone}</span>` : ''}
          ${price ? `<span style="color:#fbbf24;font-weight:500;">${price}</span>` : ''}
        </div>

        <button class="btn-clip" id="btn-clip-action" ${this.isDebouncing ? 'disabled' : ''}>
          ${
            this.isDebouncing
              ? `<div class="spinner"></div> <span>Clipping...</span>`
              : `<span>⚡ Clip to Nowing</span>`
          }
        </button>
      </div>
    `;

    const clipBtn = this.shadow.getElementById('btn-clip-action');
    if (clipBtn) {
      clipBtn.addEventListener('click', () => this.handleClip());
    }
  }
}
