import React, { useEffect, useState } from 'react';
import { ExtensionConfig } from '../types';

export const Popup: React.FC = () => {
  const [config, setConfig] = useState<ExtensionConfig>({
    backendUrl: 'http://localhost:8000',
    patToken: '',
    workspaceId: 1,
    autoDetect: true,
  });

  const [offlineCount, setOfflineCount] = useState<number>(0);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'failed'>('idle');
  const [statusMessage, setStatusMessage] = useState<string>('');

  useEffect(() => {
    // Load config and offline count
    chrome.runtime.sendMessage({ action: 'GET_CONFIG' }, (res) => {
      if (res) setConfig(res);
    });

    chrome.runtime.sendMessage({ action: 'GET_OFFLINE_COUNT' }, (res) => {
      if (res?.count !== undefined) setOfflineCount(res.count);
    });
  }, []);

  const handleSave = async (e: React.FormEvent) => {
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
      const url = `${config.backendUrl.replace(/\/$/, '')}/api/v1/workspaces/${config.workspaceId}/leads`;
      const res = await fetch(url, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${config.patToken.trim()}`,
        },
      });

      if (res.ok || res.status === 403) {
        // Even if 403 on full leads list, server is reachable with CORS
        setTestStatus('success');
        setStatusMessage('✓ Backend connection verified!');
      } else {
        setTestStatus('failed');
        setStatusMessage(`✗ Error: ${res.statusText || 'Failed to connect'}`);
      }
    } catch (err: any) {
      setTestStatus('failed');
      setStatusMessage(`✗ Network error: ${err.message || 'Check URL'}`);
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
    <div style={{ padding: '16px', boxSizing: 'border-box' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '20px' }}>⚡</span>
          <span style={{ fontWeight: 700, fontSize: '15px', color: '#6366f1' }}>Nowing Lead Clipper</span>
        </div>
        <span
          style={{
            fontSize: '11px',
            padding: '2px 8px',
            borderRadius: '9999px',
            backgroundColor: config.patToken ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
            color: config.patToken ? '#34d399' : '#f87171',
            fontWeight: 600,
          }}
        >
          {config.patToken ? 'Connected' : 'Token Required'}
        </span>
      </div>

      {/* Status banner */}
      {statusMessage && (
        <div
          style={{
            padding: '8px 12px',
            borderRadius: '6px',
            fontSize: '12px',
            marginBottom: '12px',
            backgroundColor: statusMessage.startsWith('✓') ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
            color: statusMessage.startsWith('✓') ? '#34d399' : '#f87171',
            border: `1px solid ${statusMessage.startsWith('✓') ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)'}`,
          }}
        >
          {statusMessage}
        </div>
      )}

      {/* Settings Form */}
      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div>
          <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>
            Backend API URL
          </label>
          <input
            type="text"
            value={config.backendUrl}
            onChange={(e) => setConfig({ ...config, backendUrl: e.target.value })}
            placeholder="http://localhost:8000"
            style={{
              width: '100%',
              padding: '8px 10px',
              borderRadius: '6px',
              border: '1px solid #334155',
              backgroundColor: '#1e293b',
              color: '#f8fafc',
              fontSize: '13px',
              boxSizing: 'border-box',
              outline: 'none',
            }}
          />
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>
            Workspace ID
          </label>
          <input
            type="number"
            value={config.workspaceId || 1}
            onChange={(e) => setConfig({ ...config, workspaceId: parseInt(e.target.value, 10) || 1 })}
            style={{
              width: '100%',
              padding: '8px 10px',
              borderRadius: '6px',
              border: '1px solid #334155',
              backgroundColor: '#1e293b',
              color: '#f8fafc',
              fontSize: '13px',
              boxSizing: 'border-box',
              outline: 'none',
            }}
          />
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>
            Personal Access Token (`leads:clipper:write`)
          </label>
          <input
            type="password"
            value={config.patToken}
            onChange={(e) => setConfig({ ...config, patToken: e.target.value })}
            placeholder="nw_pat_..."
            style={{
              width: '100%',
              padding: '8px 10px',
              borderRadius: '6px',
              border: '1px solid #334155',
              backgroundColor: '#1e293b',
              color: '#f8fafc',
              fontSize: '13px',
              boxSizing: 'border-box',
              outline: 'none',
            }}
          />
        </div>

        <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
          <button
            type="submit"
            disabled={isSaving}
            style={{
              flex: 1,
              padding: '8px 12px',
              borderRadius: '6px',
              backgroundColor: '#6366f1',
              color: '#ffffff',
              border: 'none',
              fontWeight: 600,
              fontSize: '13px',
              cursor: 'pointer',
            }}
          >
            {isSaving ? 'Saving...' : 'Save Config'}
          </button>

          <button
            type="button"
            onClick={handleTestConnection}
            disabled={testStatus === 'testing'}
            style={{
              padding: '8px 12px',
              borderRadius: '6px',
              backgroundColor: '#334155',
              color: '#f8fafc',
              border: 'none',
              fontWeight: 500,
              fontSize: '13px',
              cursor: 'pointer',
            }}
          >
            {testStatus === 'testing' ? 'Testing...' : 'Test'}
          </button>
        </div>
      </form>

      {/* Offline Buffer & Sync Section */}
      <div
        style={{
          marginTop: '16px',
          padding: '12px',
          borderRadius: '8px',
          backgroundColor: '#1e293b',
          border: '1px solid #334155',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span style={{ fontSize: '12px', fontWeight: 600, color: '#cbd5e1' }}>Offline Sync Queue</span>
          <span
            style={{
              fontSize: '11px',
              padding: '2px 6px',
              borderRadius: '4px',
              backgroundColor: offlineCount > 0 ? '#f59e0b' : '#475569',
              color: '#ffffff',
              fontWeight: 700,
            }}
          >
            {offlineCount} pending
          </span>
        </div>

        <p style={{ fontSize: '11px', color: '#94a3b8', margin: '0 0 10px 0' }}>
          Leads captured while disconnected or server unreachable are stored safely in local buffer.
        </p>

        <button
          type="button"
          onClick={handleSyncOffline}
          disabled={offlineCount === 0 || isSyncing}
          style={{
            width: '100%',
            padding: '6px 10px',
            borderRadius: '6px',
            backgroundColor: offlineCount > 0 ? '#059669' : '#334155',
            color: '#ffffff',
            border: 'none',
            fontSize: '12px',
            fontWeight: 600,
            cursor: offlineCount > 0 ? 'pointer' : 'not-allowed',
            opacity: offlineCount > 0 ? 1 : 0.6,
          }}
        >
          {isSyncing ? 'Syncing...' : 'Sync Pending Leads'}
        </button>
      </div>
    </div>
  );
};
