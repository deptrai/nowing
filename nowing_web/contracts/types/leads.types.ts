import { z } from "zod";

export const leadStatusSchema = z.enum([
	"new",
	"open",
	"contacted",
	"qualified",
	"converted",
	"lost",
	"pending",
]);

export type LeadStatus = z.infer<typeof leadStatusSchema>;

const scoreField = z.number().refine((v) => Number.isFinite(v) && v >= 0 && v <= 100, {
	message: "Score must be a finite number between 0 and 100",
});

export const leadSchema = z.object({
	id: z.string().uuid(),
	workspace_id: z.number(),
	client_id: z.string().nullable().optional(),
	source: z.string(),
	source_url: z.string().nullable().optional(),
	company_name: z.string(),
	domain: z.string().nullable().optional(),
	industry: z.string().nullable().optional(),
	company_size: z.string().nullable().optional(),
	location: z.string().nullable().optional(),
	tech_stack: z.array(z.string()).default([]),
	fit_score: scoreField.nullable().optional(),
	intent_score: scoreField.nullable().optional(),
	composite_score: scoreField.nullable().optional(),
	status: z.string().default("new"),
	intent: z.string().nullable().optional(),
	phone: z.string().nullable().optional(),
	price_estimate: z.string().nullable().optional(),
	content_snippet: z.string().nullable().optional(),
	author: z.string().nullable().optional(),
	enriched: z.boolean().default(false),
	created_at: z.string(),
	updated_at: z.string().nullable().optional(),
});

export type Lead = z.infer<typeof leadSchema>;

export const leadListResponseSchema = z.object({
	items: z.array(leadSchema),
	total: z.number(),
	limit: z.number(),
	offset: z.number(),
});

export type LeadListResponse = z.infer<typeof leadListResponseSchema>;

export const decisionMakerSchema = z.object({
	name: z.string(),
	title: z.string(),
	linkedin_url: z.string().nullable().optional(),
	email: z.string().nullable().optional(),
	phone: z.string().nullable().optional(),
	confidence: z
		.number()
		.refine((v) => Number.isFinite(v) && v >= 0 && v <= 1, {
			message: "Confidence must be a finite number between 0 and 1",
		})
		.default(1.0),
});

export type DecisionMaker = z.infer<typeof decisionMakerSchema>;

export const tenderSummarySchema = z.object({
	tender_number: z.string(),
	title: z.string(),
	procuring_entity: z.string(),
	budget_vnd: z.number().nullable().optional(),
	close_date: z.string().nullable().optional(),
	source_url: z.string().nullable().optional(),
});

export type TenderSummary = z.infer<typeof tenderSummarySchema>;

export const hiringSignalSchema = z.object({
	title: z.string(),
	department: z.string().nullable().optional(),
	platform: z.string(),
	posted_date: z.string().nullable().optional(),
	url: z.string().nullable().optional(),
});

export type HiringSignal = z.infer<typeof hiringSignalSchema>;

export const legalEntitySchema = z.object({
	tax_id: z.string().nullable().optional(),
	legal_name: z.string(),
	representative: z.string().nullable().optional(),
	charter_capital: z.string().nullable().optional(),
	founding_date: z.string().nullable().optional(),
	headquarters: z.string().nullable().optional(),
	status: z.string().default("active"),
});

export type LegalEntity = z.infer<typeof legalEntitySchema>;

export const companyGraphSchema = z.object({
	company_name: z.string(),
	legal_entity: legalEntitySchema.nullable().optional(),
	decision_makers: z.array(decisionMakerSchema).default([]),
	tenders: z.array(tenderSummarySchema).default([]),
	hiring_signals: z.array(hiringSignalSchema).default([]),
	hiring_velocity_pct: z
		.number()
		.refine((v) => Number.isFinite(v), {
			message: "Hiring velocity must be a finite number",
		})
		.nullable()
		.optional(),
	active_jobs_count: z
		.number()
		.refine((v) => Number.isFinite(v) && v >= 0 && Number.isInteger(v), {
			message: "Active jobs count must be a finite non-negative integer",
		})
		.default(0),
});

export type CompanyGraph = z.infer<typeof companyGraphSchema>;

export interface ListLeadsParams {
	client_id?: string;
	source?: string;
	intent?: string;
	min_score?: number;
	status?: string;
	search?: string;
	sort?: string;
	limit?: number;
	offset?: number;
}

export const zaloDraftResponseSchema = z.object({
	lead_id: z.string(),
	phone: z.string(),
	clean_phone: z.string(),
	zalo_url: z.string(),
	draft: z.string(),
	company_name: z.string(),
	log_id: z.string().nullable().optional(),
});

export type ZaloDraftResponse = z.infer<typeof zaloDraftResponseSchema>;

export const znsSendRequestSchema = z.object({
	template_id: z.string(),
	template_data: z.record(z.string(), z.any()),
	tracking_id: z.string().optional(),
	consent_confirmed: z.boolean().default(false),
	oa_id: z.string().optional(),
	mode: z.string().optional(),
});

export type ZnsSendRequest = z.infer<typeof znsSendRequestSchema>;

export const znsSendResponseSchema = z.object({
	status: z.string(),
	msg_id: z.string().nullable().optional(),
	recipient_phone: z.string(),
	error: z.string().nullable().optional(),
	log_id: z.string().nullable().optional(),
});

export type ZnsSendResponse = z.infer<typeof znsSendResponseSchema>;

export const buyerPersonaSchema = z.object({
	title: z.string(),
	industry: z.string(),
	company_size: z.string(),
	pain_points: z.array(z.string()).default([]),
	buying_triggers: z.array(z.string()).default([]),
});

export type BuyerPersona = z.infer<typeof buyerPersonaSchema>;

export const filterPresetsSchema = z.object({
	platforms: z.array(z.string()).default([]),
	intent: z.string().default("BÁN"),
	target_industries: z.array(z.string()).default([]),
	locations: z.array(z.string()).default([]),
	company_size_range: z.string().nullable().optional(),
});

export type FilterPresets = z.infer<typeof filterPresetsSchema>;

export const reverseIcpRequestSchema = z.object({
	url: z.string().min(1, "URL không được để trống"),
	custom_instructions: z.string().nullable().optional(),
});

export type ReverseIcpRequest = z.infer<typeof reverseIcpRequestSchema>;

export const reverseIcpResponseSchema = z.object({
	company_name: z.string(),
	domain: z.string(),
	value_proposition: z.string(),
	industry: z.string(),
	target_buyer_personas: z
		.array(buyerPersonaSchema)
		.nullish()
		.transform((v) => v ?? []),
	suggested_search_queries: z
		.array(z.string())
		.nullish()
		.transform((v) => v ?? []),
	negative_keywords: z
		.array(z.string())
		.nullish()
		.transform((v) => v ?? []),
	filter_presets: filterPresetsSchema.default({
		platforms: [],
		intent: "BÁN",
		target_industries: [],
		locations: [],
	}),
	chat_starter_prompts: z
		.array(z.string())
		.nullish()
		.transform((v) => v ?? []),
	raw_metadata: z.record(z.string(), z.any()).optional().default({}),
});

export type ReverseIcpResponse = z.infer<typeof reverseIcpResponseSchema>;
