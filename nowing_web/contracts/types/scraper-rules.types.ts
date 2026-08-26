export interface RuleDelays {
	request_ms: number;
	retry_base_ms: number;
}

export interface RuleRetries {
	max_attempts: number;
	statuses: number[];
}

export interface RuleCircuitBreaker {
	error_threshold_pct: number;
	min_calls: number;
	trip_duration_seconds: number;
	tripped: boolean;
}

export interface RuleSchema {
	selectors: Record<string, string>;
	regexes: Record<string, string>;
	delays: RuleDelays;
	retries: RuleRetries;
	circuit_breaker: RuleCircuitBreaker;
}

export interface ScraperRuleListItem {
	platform: string;
	version: number;
	is_active: boolean;
	updated_at: string;
	updated_by: string | null;
}

export interface ScraperRuleListResponse {
	items: ScraperRuleListItem[];
	total: number;
}

export interface ScraperRuleRead {
	id: number;
	platform: string;
	version: number;
	rule_schema: RuleSchema;
	is_active: boolean;
	created_by_user_id: string | null;
	updated_by_user_id: string | null;
	created_at: string;
	updated_at: string;
}
