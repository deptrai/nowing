/**
 * Offline buffer & queue manager for lead resilience (AC-4).
 * Stores unsent leads when offline and provides batch sync.
 */

import { LeadClipPayload, OfflineQueuedLead } from '../types';

const QUEUE_STORAGE_KEY = 'nowing_clipper_offline_queue';

export async function getOfflineQueue(): Promise<OfflineQueuedLead[]> {
  return new Promise((resolve) => {
    chrome.storage.local.get([QUEUE_STORAGE_KEY], (result) => {
      resolve(result[QUEUE_STORAGE_KEY] || []);
    });
  });
}

export async function enqueueLead(
  payload: LeadClipPayload,
  workspaceId: number,
  lastError?: string
): Promise<OfflineQueuedLead[]> {
  const queue = await getOfflineQueue();
  const queuedLead: OfflineQueuedLead = {
    id: `offline_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
    payload,
    workspaceId,
    queuedAt: new Date().toISOString(),
    retryCount: 0,
    lastError,
  };
  const updated = [...queue, queuedLead];
  await new Promise<void>((resolve) => {
    chrome.storage.local.set({ [QUEUE_STORAGE_KEY]: updated }, () => resolve());
  });
  await updateBadge(updated.length);
  return updated;
}

export async function removeQueuedLead(id: string): Promise<OfflineQueuedLead[]> {
  const queue = await getOfflineQueue();
  const updated = queue.filter((item) => item.id !== id);
  await new Promise<void>((resolve) => {
    chrome.storage.local.set({ [QUEUE_STORAGE_KEY]: updated }, () => resolve());
  });
  await updateBadge(updated.length);
  return updated;
}

export async function clearOfflineQueue(): Promise<void> {
  await new Promise<void>((resolve) => {
    chrome.storage.local.remove([QUEUE_STORAGE_KEY], () => resolve());
  });
  await updateBadge(0);
}

export async function updateBadge(count: number): Promise<void> {
  try {
    if (count > 0) {
      await chrome.action.setBadgeText({ text: count.toString() });
      await chrome.action.setBadgeBackgroundColor({ color: '#f59e0b' }); // Amber warning badge
    } else {
      await chrome.action.setBadgeText({ text: '' });
    }
  } catch (err) {
    console.warn('Failed to update extension badge:', err);
  }
}
