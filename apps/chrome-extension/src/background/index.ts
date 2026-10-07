/**
 * Background Service Worker for Nowing Lead Clipper (INV-24.5 / Story 24.4).
 * Manages isolated PAT tokens, dispatches REST calls, and manages the offline buffer.
 */

import {
  enqueueLead,
  getOfflineQueue,
  removeQueuedLead,
  updateBadge,
} from '../storage/offline_queue.js';
import { getConfig, saveConfig } from '../storage/token_store.js';
import { ExtensionMessage, LeadClipPayload, LeadClipResponse } from '../types/index.js';

// Update initial badge on service worker start
getOfflineQueue().then((q) => updateBadge(q.length));

chrome.runtime.onMessage.addListener((message: ExtensionMessage, _sender, sendResponse) => {
  handleMessage(message)
    .then((res) => sendResponse(res))
    .catch((err) =>
      sendResponse({ success: false, message: err instanceof Error ? err.message : 'Error' }));
  return true; // Keep async response channel open
});

async function handleMessage(message: ExtensionMessage): Promise<unknown> {
  switch (message.action) {
    case 'CLIP_LEAD':
      return handleClipLead(message.payload);

    case 'GET_CONFIG':
      return getConfig();

    case 'SAVE_CONFIG': {
      const updated = await saveConfig(message.config);
      return { success: true, config: updated };
    }

    case 'GET_OFFLINE_COUNT': {
      const queue = await getOfflineQueue();
      return { count: queue.length };
    }

    case 'SYNC_OFFLINE_QUEUE':
      return handleSyncOfflineQueue();

    case 'GET_ZALO_CONTEXT':
      return handleZaloContext(message.phone);

    case 'PING':
      return { status: 'ok', timestamp: Date.now() };

    default:
      return { success: false, message: 'Unknown action' };
  }
}

async function handleClipLead(payload: LeadClipPayload): Promise<unknown> {
  const config = await getConfig();

  if (!config.patToken) {
    return {
      success: false,
      message: 'Please set Personal Access Token (PAT) in Extension popup',
    };
  }

  if (!config.workspaceId) {
    return {
      success: false,
      message: 'Please configure active Workspace ID in Extension popup',
    };
  }

  const endpoint = `${config.backendUrl.replace(/\/$/, '')}/api/v1/workspaces/${config.workspaceId}/leads/clip`;

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${config.patToken.trim()}`,
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({ detail: response.statusText }));
      const errorMsg = errBody.detail || `Server error (${response.status})`;

      // If server error or token expired/invalid, save to offline buffer if 5xx or network
      if (response.status >= 500) {
        await enqueueLead(payload, config.workspaceId, errorMsg);
        return { success: false, queued: true, message: errorMsg };
      }

      return { success: false, message: errorMsg };
    }

    const data: LeadClipResponse = await response.json();
    return data;
  } catch (netErr) {
    // Network disconnection / fetch failure: save to offline buffer (AC-4)
    const msg = netErr instanceof Error ? netErr.message : 'Network disconnected';
    await enqueueLead(payload, config.workspaceId, msg);
    return {
      success: false,
      queued: true,
      message: 'Network offline. Saved to offline sync buffer.',
    };
  }
}

/**
 * Story 37.4: fetch co-pilot context for a phone detected on chat.zalo.me.
 * PAT never leaves the service worker (INV-24.5); the content script only
 * receives the sanitized context payload.
 */

// Per-phone cache so SPA conversation flips don't refetch/rebuild.
const ZALO_CONTEXT_TTL_MS = 60_000;
const zaloContextCache = new Map<string, { context: unknown; ts: number }>();

function detailToMessage(detail: unknown, fallback: string): string {
  // FastAPI 422 returns detail as an array of {msg, loc, ...} objects.
  if (Array.isArray(detail)) return detail[0]?.msg || fallback;
  return typeof detail === 'string' && detail ? detail : fallback;
}

async function handleZaloContext(phone: string): Promise<unknown> {
  const config = await getConfig();

  if (!config.patToken?.trim()) {
    return { success: false, message: 'Please set Personal Access Token (PAT) in Extension popup' };
  }
  if (!config.workspaceId) {
    return { success: false, message: 'Please configure active Workspace ID in Extension popup' };
  }

  const cached = zaloContextCache.get(phone);
  if (cached && Date.now() - cached.ts < ZALO_CONTEXT_TTL_MS) {
    return { success: true, context: cached.context };
  }

  const endpoint =
    `${config.backendUrl.replace(/\/$/, '')}` +
    `/api/v1/workspaces/${config.workspaceId}/leads/copilot-context` +
    `?phone=${encodeURIComponent(phone)}`;

  try {
    const response = await fetch(endpoint, {
      method: 'GET',
      headers: { Authorization: `Bearer ${config.patToken.trim()}` },
      signal: AbortSignal.timeout(15_000),
    });

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({ detail: response.statusText }));
      return {
        success: false,
        message: detailToMessage(errBody.detail, `Server error (${response.status})`),
      };
    }

    const context = await response.json();
    zaloContextCache.set(phone, { context, ts: Date.now() });
    return { success: true, context };
  } catch (netErr) {
    const name = netErr instanceof Error ? netErr.name : '';
    let message = 'Network offline';
    if (name === 'TimeoutError' || name === 'AbortError') {
      message = 'Request timed out';
    } else if (netErr instanceof Error) {
      message = netErr.message;
    }
    return { success: false, message };
  }
}

async function handleSyncOfflineQueue(): Promise<{ synced: number; failed: number; remaining: number }> {
  const config = await getConfig();
  const queue = await getOfflineQueue();

  if (queue.length === 0) {
    return { synced: 0, failed: 0, remaining: 0 };
  }

  // Cannot sync without a PAT; leave the queue intact for a later retry.
  if (!config.patToken?.trim()) {
    return { synced: 0, failed: queue.length, remaining: queue.length };
  }

  let synced = 0;
  let failed = 0;

  for (const item of queue) {
    const wsId = item.workspaceId || config.workspaceId;
    if (!wsId) {
      // No workspace id available — this item is unrecoverable.
      await removeQueuedLead(item.id);
      continue;
    }

    const endpoint = `${config.backendUrl.replace(/\/$/, '')}/api/v1/workspaces/${wsId}/leads/clip`;

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${config.patToken.trim()}`,
        },
        body: JSON.stringify(item.payload),
      });

      if (res.ok) {
        await removeQueuedLead(item.id);
        synced++;
      } else if (res.status >= 400 && res.status < 500) {
        // 4xx means the payload or auth is rejected; retrying will not help.
        console.warn(
          `Offline lead ${item.id} rejected with ${res.status} ${res.statusText}; dropping`,
        );
        await removeQueuedLead(item.id);
      } else {
        // 5xx / other errors: keep in queue for a later retry.
        failed++;
      }
    } catch {
      failed++;
    }
  }

  const remainingQueue = await getOfflineQueue();
  const remaining = remainingQueue.length;
  await updateBadge(remaining);
  return { synced, failed, remaining };
}
