/**
 * Core type definitions for Nowing Lead Clipper Extension (INV-24.5 / Story 24.4).
 */

export type SourcePlatform =
  | 'facebook'
  | 'batdongsan'
  | 'topcv'
  | 'linkedin'
  | 'chotot'
  | 'custom'
  | 'generic';

export interface LeadClipPayload {
  source_canonical_url: string;
  source_platform: SourcePlatform;
  contact_name?: string | null;
  phone?: string | null;
  email?: string | null;
  company_name?: string | null;
  post_content?: string | null;
  price?: string | null;
  location?: string | null;
  metadata?: Record<string, any>;
  dedupe_hash?: string | null;
}

export interface LeadClipResponse {
  success: boolean;
  lead_id: string;
  workspace_id: number;
  dedupe_hash: string;
  is_duplicate: boolean;
  source_platform: string;
  message: string;
  created_at: string;
}

export interface ExtensionConfig {
  backendUrl: string;
  patToken: string;
  workspaceId: number | null;
  autoDetect: boolean;
}

export interface OfflineQueuedLead {
  id: string;
  payload: LeadClipPayload;
  workspaceId: number;
  queuedAt: string;
  retryCount: number;
  lastError?: string;
}

export type ExtensionMessage =
  | { action: 'CLIP_LEAD'; payload: LeadClipPayload }
  | { action: 'GET_CONFIG' }
  | { action: 'SAVE_CONFIG'; config: Partial<ExtensionConfig> }
  | { action: 'GET_OFFLINE_COUNT' }
  | { action: 'SYNC_OFFLINE_QUEUE' }
  | { action: 'DETECTED_LEAD_INFO'; payload: LeadClipPayload | null }
  | { action: 'GET_ZALO_CONTEXT'; phone: string }
  | { action: 'PING' };

// --- Story 37.4: Zalo Co-pilot overlay (AD-118) ---

export interface ZaloCopilotSignal {
  signal_type: string;
  confidence: number;
  detected_at: string;
  source_url: string | null;
}

export interface ZaloCopilotLead {
  lead_id: string;
  company_name: string;
  contact_name: string | null;
  contact_title: string | null;
  industry: string | null;
  location: string | null;
  domain: string | null;
  status: string;
  intent_score: number | null;
}

export interface ZaloCopilotContext {
  matched: boolean;
  phone_e164: string | null;
  dnc_blocked: boolean;
  dnc_reason: string | null;
  lead: ZaloCopilotLead | null;
  signals: ZaloCopilotSignal[];
  pitch_short: string | null;
  pitch_with_link: string | null;
  pitch_portal_url: string | null;
}
