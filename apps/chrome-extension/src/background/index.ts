/**
 * Background Service Worker for Nowing Lead Clipper (INV-24.5 / Story 24.4).
 * Manages isolated PAT tokens, dispatches REST calls, and manages the offline buffer.
 */

import {
  clearOfflineQueue,
  enqueueLead,
  getOfflineQueue,
  removeQueuedLead,
  updateBadge,
} from '../storage/offline_queue';
import { getConfig, saveConfig } from '../storage/token_store';
import { ExtensionMessage, LeadClipPayload, LeadClipResponse } from '../types';

// Update initial badge on service worker start
getOfflineQueue().then((q) => updateBadge(q.length));

chrome.runtime.onMessage.addListener((message: ExtensionMessage, _sender, sendResponse) => {
  handleMessage(message)
    .then((res) => sendResponse(res))
    .catch((err) => sendResponse({ success: false, message: err.message }));
  return true; // Keep async response channel open
});

async function handleMessage(message: ExtensionMessage): Promise<any> {
  switch (message.action) {
    case 'CLIP_LEAD':
      return await handleClipLead(message.payload);

    case 'GET_CONFIG':
      return await getConfig();

    case 'SAVE_CONFIG':
      const updated = await saveConfig(message.config);
      return { success: true, config: updated };

    case 'GET_OFFLINE_COUNT':
      const queue = await getOfflineQueue();
      return { count: queue.length };

    case 'SYNC_OFFLINE_QUEUE':
      return await handleSyncOfflineQueue();

    case 'PING':
      return { status: 'ok', timestamp: Date.now() };

    default:
      return { success: false, message: 'Unknown action' };
  }
}

async function handleClipLead(payload: LeadClipPayload): Promise<any> {
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
  } catch (netErr: any) {
    // Network disconnection / fetch failure: save to offline buffer (AC-4)
    await enqueueLead(payload, config.workspaceId, netErr.message || 'Network disconnected');
    return {
      success: false,
      queued: true,
      message: 'Network offline. Saved to offline sync buffer.',
    };
  }
}

async function handleSyncOfflineQueue(): Promise<{ synced: number; failed: number; remaining: number }> {
  const config = await getConfig();
  const queue = await getOfflineQueue();

  if (queue.length === 0) {
    return { synced: 0, failed: 0, remaining: 0 };
  }

  let synced = 0;
  let failed = 0;

  for (const item of queue) {
    const wsId = item.workspaceId || config.workspaceId;
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
      } else {
        failed++;
      }
    } catch {
      failed++;
    }
  }

  const remaining = (await getOfflineQueue()).length;
  await updateBadge(remaining);
  return { synced, failed, remaining };
}
