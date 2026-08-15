export type PlanType = "seat" | "outcome" | "hybrid";

export interface OutcomeEventRead {
	id: string;
	workspace_id: number;
	event_type: string;
	lead_id: string;
	sequence_id?: string | null;
	attribution: string;
	cost_micros: number;
	outcome_metadata: Record<string, unknown>;
	created_at: string;
}

export interface PricingPlanRead {
	id: string;
	workspace_id: number;
	plan_type: PlanType;
	seat_price?: number | null;
	outcome_rates_json: Record<string, number>;
	billing_period?: string | null;
	is_active: boolean;
}

export interface PricingPlanUpdate {
	plan_type?: PlanType;
	seat_price?: number;
	outcome_rates_json?: Record<string, number>;
	billing_period?: string;
}

export interface ServiceBreakdownItem {
	category: string;
	total_tokens: number;
	cost_micros: number;
	event_count: number;
}

export interface ServiceBreakdownResponse {
	workspace_id: number;
	start_date: string;
	end_date: string;
	items: ServiceBreakdownItem[];
}
