/**
 * Isolated Token & Config Storage for Background Service Worker (INV-24.5).
 *
 * ponytail: uses chrome.storage.session instead of chrome.storage.local so the
 * PAT is never persisted to disk. The tradeoff is settings are lost when the
 * browser closes; if persistence is needed, encrypt with a user-supplied
 * password or OS keychain instead of reverting to local.
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
    chrome.storage.session.get([STORAGE_KEY], (result) => {
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
    chrome.storage.session.set({ [STORAGE_KEY]: updated }, () => {
      resolve(updated);
    });
  });
}

export async function clearConfig(): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.session.remove([STORAGE_KEY], () => {
      resolve();
    });
  });
}
