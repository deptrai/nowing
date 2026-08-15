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
