/**
 * Isolated Token & Config Storage for Background Service Worker (INV-24.5).
 */

import { ExtensionConfig } from '../types';

const STORAGE_KEY = 'nowing_clipper_config';

const DEFAULT_CONFIG: ExtensionConfig = {
  backendUrl: 'http://localhost:8000',
  patToken: '',
  workspaceId: 1,
  autoDetect: true,
};

export async function getConfig(): Promise<ExtensionConfig> {
  return new Promise((resolve) => {
    chrome.storage.local.get([STORAGE_KEY], (result) => {
      if (result[STORAGE_KEY]) {
        resolve({ ...DEFAULT_CONFIG, ...result[STORAGE_KEY] });
      } else {
        resolve(DEFAULT_CONFIG);
      }
    });
  });
}

export async function saveConfig(config: Partial<ExtensionConfig>): Promise<ExtensionConfig> {
  const current = await getConfig();
  const updated: ExtensionConfig = { ...current, ...config };
  return new Promise((resolve) => {
    chrome.storage.local.set({ [STORAGE_KEY]: updated }, () => {
      resolve(updated);
    });
  });
}

export async function clearConfig(): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.local.remove([STORAGE_KEY], () => {
      resolve();
    });
  });
}
