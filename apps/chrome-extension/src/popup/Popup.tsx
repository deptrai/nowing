import React, { useEffect, useState } from 'react';
import { ExtensionConfig } from '../types/index.js';
import './popup.css';

const DEFAULT_BACKEND_URL = 'http://localhost:8000';

// pi-lens-ignore: high-complexity — single popup component, splitting adds files for no reuse
export const Popup: React.FC = () => {
  const [config, setConfig] = useState<ExtensionConfig>({
    backendUrl: DEFAULT_BACKEND_URL,
    patToken: '',
    workspaceId: 1,
    autoDetect: true,
  });

  const [offlineCount, setOfflineCount] = useState(0);
  const [isSaving, setIsSaving] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'failed'>('idle');
  const [statusMessage, setStatusMessage] = useState('');

  useEffect(() => {
    // Load config and offline count
    chrome.runtime.sendMessage({ action: 'GET_CONFIG' }, (res) => {
      if (res) setConfig(res);
    });

    chrome.runtime.sendMessage({ action: 'GET_OFFLINE_COUNT' }, (res) => {
      if (res?.count !== undefined) setOfflineCount(res.count);
    });
  }, []);

  const handleSave = async (e: React.SubmitEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsSaving(true);
    setStatusMessage('');

    chrome.runtime.sendMessage(
      {
        action: 'SAVE_CONFIG',
        config: {
          backendUrl: config.backendUrl.trim(),
          patToken: config.patToken.trim(),
          workspaceId: Number(config.workspaceId) || 1,
        },
      },
      (res) => {
        setIsSaving(false);
        if (res?.success) {
          setStatusMessage('✓ Settings saved successfully');
          setTimeout(() => setStatusMessage(''), 3000);
        }
      }
    );
  };

  const handleTestConnection = async () => {
    setTestStatus('testing');
    setStatusMessage('');

    try {
      const url = `${config.backendUrl.replace(/\/$/, '')}/health`;
      const res = await fetch(url, { method: 'GET' });

      if (res.ok) {
        setTestStatus('success');
        setStatusMessage('✓ Backend connection verified!');
      } else {
        setTestStatus('failed');
        setStatusMessage(`✗ Error: ${res.statusText || 'Failed to connect'}`);
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Check URL';
      setTestStatus('failed');
      setStatusMessage(`✗ Network error: ${errorMessage}`);
    } finally {
      setTimeout(() => setTestStatus('idle'), 4000);
    }
  };

  const handleSyncOffline = () => {
    setIsSyncing(true);
    chrome.runtime.sendMessage({ action: 'SYNC_OFFLINE_QUEUE' }, (res) => {
      setIsSyncing(false);
      if (res) {
        setOfflineCount(res.remaining || 0);
        setStatusMessage(`✓ Synced ${res.synced} leads (${res.failed} failed)`);
        setTimeout(() => setStatusMessage(''), 4000);
      }
    });
  };

  return (
    <div className="popup-container">
      {/* Header */}
      <div className="popup-header">
        <div className="popup-header-title-group">
          <span className="popup-header-icon">⚡</span>
          <span className="popup-header-title">Nowing Lead Clipper</span>
        </div>
        <span
          className={`popup-badge ${
            config.patToken ? 'popup-badge-connected' : 'popup-badge-disconnected'
          }`}
        >
          {config.patToken ? 'Connected' : 'Token Required'}
        </span>
      </div>

      {/* Status banner */}
      {statusMessage && (
        <div
          className={`popup-status-message ${
            statusMessage.startsWith('✓') ? 'popup-status-success' : 'popup-status-error'
          }`}
        >
          {statusMessage}
        </div>
      )}

      {/* Settings Form */}
      <form onSubmit={handleSave} className="popup-form">
        <div>
          <label htmlFor="backend-url" className="popup-label">
            Backend API URL
          </label>
          <input
            id="backend-url"
            type="text"
            value={config.backendUrl}
            onChange={(e) => setConfig({ ...config, backendUrl: e.target.value })}
            placeholder={DEFAULT_BACKEND_URL}
            className="popup-input"
          />
        </div>

        <div>
          <label htmlFor="workspace-id" className="popup-label">
            Workspace ID
          </label>
          <input
            id="workspace-id"
            type="number"
            value={config.workspaceId || 1}
            onChange={(e) => setConfig({ ...config, workspaceId: parseInt(e.target.value, 10) || 1 })}
            className="popup-input"
          />
        </div>

        <div>
          <label htmlFor="pat-token" className="popup-label">
            Personal Access Token (`leads:clipper:write`)
          </label>
          <input
            id="pat-token"
            type="password"
            value={config.patToken}
            onChange={(e) => setConfig({ ...config, patToken: e.target.value })}
            placeholder="nw_pat_..."
            className="popup-input"
          />
        </div>

        <div className="popup-form-actions">
          <button
            type="submit"
            disabled={isSaving}
            className="popup-btn popup-btn-primary"
          >
            {isSaving ? 'Saving...' : 'Save Config'}
          </button>

          <button
            type="button"
            onClick={handleTestConnection}
            disabled={testStatus === 'testing'}
            className="popup-btn popup-btn-secondary"
          >
            {testStatus === 'testing' ? 'Testing...' : 'Test'}
          </button>
        </div>
      </form>

      {/* Offline Buffer & Sync Section */}
      <div className="popup-offline-card">
        <div className="popup-offline-header">
          <span className="popup-offline-title">Offline Sync Queue</span>
          <span
            className={`popup-offline-badge ${
              offlineCount > 0 ? 'popup-offline-badge-pending' : 'popup-offline-badge-empty'
            }`}
          >
            {offlineCount} pending
          </span>
        </div>

        <p className="popup-offline-desc">
          Leads captured while disconnected or server unreachable are stored safely in local buffer.
        </p>

        <button
          type="button"
          onClick={handleSyncOffline}
          disabled={offlineCount === 0 || isSyncing}
          className={`popup-btn popup-btn-sync ${
            offlineCount > 0 ? 'popup-btn-sync-active' : 'popup-btn-sync-disabled'
          }`}
        >
          {isSyncing ? 'Syncing...' : 'Sync Pending Leads'}
        </button>
      </div>
    </div>
  );
};
