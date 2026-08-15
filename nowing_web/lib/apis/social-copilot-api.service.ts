import { baseApiService } from "./base-api.service";

export interface FormattingQuirks {
	emoji_density: "none" | "low" | "medium" | "high";
	bullet_style: "numbered_list" | "bullet" | "none";
	line_break_frequency: "low" | "medium" | "high";
}

export interface VoiceProfile {
	id?: number;
	profile_name: string;
	tone: string;
	average_sentence_length: number;
	paragraph_cadence: string;
	hook_preference: string;
	vocabulary: string[];
	formatting_quirks: FormattingQuirks;
	is_active: boolean;
	created_at?: string;
}

export interface VoiceProfileListItem {
	id: number;
	profile_name: string;
	tone: string;
	is_active: boolean;
	created_at?: string;
}

export interface VoiceProfileListResponse {
	items: VoiceProfileListItem[];
	total: number;
}

export interface OutlierPostItem {
	id?: number;
	platform: string;
	external_post_id: string;
	author_name?: string;
	author_id?: string;
	author_url?: string;
	post_url?: string;
	content: string;
	reactions_count: number;
	comments_count: number;
	shares_count: number;
	engagement_score: number;
	baseline_ratio: number;
	hook_taxonomy?: string;
	why_it_worked?: string;
	published_at?: string;
}

export interface OutlierPostsResponse {
	items: OutlierPostItem[];
	total: number;
	degraded: boolean;
}

export interface DeconstructedElements {
	hook: string;
	re_hook: string;
	body: string;
	cta: string;
	taxonomy: "contrarian_hook" | "story_shift" | "value_list" | "data_reveal";
	analysis: string;
}

export interface ManualIngestResponse {
	platform: string;
	source_url?: string;
	original_text_redacted: string;
	deconstructed_elements: DeconstructedElements;
}

export interface DraftVariation {
	variation_letter: "A" | "B" | "C";
	content: string;
	angle: "contrarian" | "framework" | "case_study";
	estimated_reading_time_sec: number;
	is_thread: boolean;
	thread_tweets: string[];
}

export interface GenerateDraftsResponse {
	drafts: DraftVariation[];
	token_usage?: Record<string, unknown>;
	billing_event_id?: string;
}

class SocialCopilotApiService {
	async createVoiceProfile(
		workspaceId: number | string,
		payload: { sample_text: string; profile_name: string; platform?: string }
	): Promise<VoiceProfile> {
		return baseApiService.post<VoiceProfile>(
			`/api/workspaces/${workspaceId}/voice-profiles`,
			undefined,
			{ body: payload }
		);
	}

	async listVoiceProfiles(workspaceId: number | string): Promise<VoiceProfileListResponse> {
		return baseApiService.get<VoiceProfileListResponse>(
			`/api/workspaces/${workspaceId}/voice-profiles`
		);
	}

	async activateVoiceProfile(
		workspaceId: number | string,
		profileId: number
	): Promise<VoiceProfile> {
		return baseApiService.put<VoiceProfile>(
			`/api/workspaces/${workspaceId}/voice-profiles/${profileId}/activate`,
			undefined,
			{ body: {} }
		);
	}

	async getOutlierPosts(
		workspaceId: number | string,
		params?: { keywords?: string[]; min_multiplier?: number }
	): Promise<OutlierPostsResponse> {
		const searchParams = new URLSearchParams();
		if (params?.min_multiplier) {
			searchParams.append("min_multiplier", String(params.min_multiplier));
		}
		if (params?.keywords && params.keywords.length > 0) {
			for (const kw of params.keywords) {
				searchParams.append("keywords", kw);
			}
		}
		const qs = searchParams.toString();
		const url = `/api/workspaces/${workspaceId}/social-copilot/outliers${qs ? `?${qs}` : ""}`;
		return baseApiService.get<OutlierPostsResponse>(url);
	}

	async manualIngest(
		workspaceId: number | string,
		payload: { raw_text: string; source_url?: string; platform?: string }
	): Promise<ManualIngestResponse> {
		return baseApiService.post<ManualIngestResponse>(
			`/api/workspaces/${workspaceId}/social-copilot/manual-ingest`,
			undefined,
			{ body: payload }
		);
	}

	async generateViralDrafts(
		workspaceId: number | string,
		payload: {
			topic: string;
			hook_taxonomy?: string;
			voice_profile_id?: number;
			target_platform?: "twitter" | "facebook" | "linkedin" | "threads";
			n_variations?: number;
		}
	): Promise<GenerateDraftsResponse> {
		return baseApiService.post<GenerateDraftsResponse>(
			`/api/workspaces/${workspaceId}/social-copilot/generate-drafts`,
			undefined,
			{ body: payload }
		);
	}
}

export const socialCopilotApiService = new SocialCopilotApiService();
