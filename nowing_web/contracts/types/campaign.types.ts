import { z } from "zod";
import { leadSchema } from "./leads.types";

export const campaignStatusSchema = z.enum([
	"draft",
	"scheduled",
	"running",
	"paused",
	"completed",
	"failed",
]);

export type CampaignStatus = z.infer<typeof campaignStatusSchema>;

export const campaignIntentSchema = z.enum(["BÁN", "MUA", "TUYỂN", "ĐẤU THẦU", "HỢP TÁC"]);

export type CampaignIntent = z.infer<typeof campaignIntentSchema>;

export const icpVerticalTemplateSchema = z.enum([
	"b2b_saas",
	"real_estate_investor",
	"recruitment_agency",
	"gov_tender_contractor",
	"fmcg_distributor",
	"custom",
]);

export type IcpVerticalTemplate = z.infer<typeof icpVerticalTemplateSchema>;

export const icpConfigSchema = z.object({
	template: icpVerticalTemplateSchema.default("custom"),
	target_industries: z.array(z.string()).default([]),
	locations: z.array(z.string()).default([]),
	company_size_range: z.string().nullable().optional(),
	tech_stack: z.array(z.string()).default([]),
	intents: z.array(campaignIntentSchema).default(["BÁN"]),
	negative_keywords: z.array(z.string()).default([]),
	reverse_icp_url: z.string().url().nullable().optional().or(z.literal("")),
	custom_instructions: z.string().nullable().optional(),
});

export type IcpConfig = z.infer<typeof icpConfigSchema>;

export const sourceBudgetConfigSchema = z.object({
	sources: z.array(z.string()).min(1, "Phải chọn ít nhất 1 nguồn thu thập"),
	expected_leads_target: z.number().int().min(1).default(100),
	max_daily_spend_vnd: z.number().nonnegative().default(500000),
	min_fit_score: z.number().min(0).max(100).default(60),
	min_intent_score: z.number().min(0).max(100).default(50),
	max_contacts_per_lead: z.number().int().min(1).max(10).default(3),
	exclude_dnc: z.boolean().default(true),
	auto_unlock_verified_phones: z.boolean().default(false),
});

export type SourceBudgetConfig = z.infer<typeof sourceBudgetConfigSchema>;

export const campaignScheduleTypeSchema = z.enum(["once", "recurring"]);
export type CampaignScheduleType = z.infer<typeof campaignScheduleTypeSchema>;

export const launchConfigSchema = z.object({
	schedule_type: campaignScheduleTypeSchema.default("once"),
	cron_expression: z.string().nullable().optional(),
	start_time: z.string().nullable().optional(),
	auto_start: z.boolean().default(true),
	export_destination: z.enum(["workspace", "crm", "lark", "sheets"]).default("workspace"),
	notification_webhook: z.string().url().nullable().optional().or(z.literal("")),
});

export type LaunchConfig = z.infer<typeof launchConfigSchema>;

export const campaignSchema = z.object({
	id: z.string().uuid(),
	workspace_id: z.number(),
	name: z.string().min(1, "Tên chiến dịch không được để trống"),
	description: z.string().nullable().optional(),
	status: campaignStatusSchema.default("draft"),
	icp_config: icpConfigSchema,
	source_budget_config: sourceBudgetConfigSchema,
	launch_config: launchConfigSchema,
	collected_leads_count: z.number().default(0),
	qualified_leads_count: z.number().default(0),
	estimated_cost_vnd: z.number().default(0),
	created_at: z.string(),
	updated_at: z.string().nullable().optional(),
	created_by_user_id: z.string().uuid().nullable().optional(),
});

export type Campaign = z.infer<typeof campaignSchema>;

export const campaignCreateInputSchema = z.object({
	name: z.string().min(1, "Tên chiến dịch không được để trống"),
	description: z.string().nullable().optional(),
	icp_config: icpConfigSchema,
	source_budget_config: sourceBudgetConfigSchema,
	launch_config: launchConfigSchema,
});

export type CampaignCreateInput = z.infer<typeof campaignCreateInputSchema>;

export const campaignUpdateInputSchema = campaignCreateInputSchema.partial().extend({
	status: campaignStatusSchema.optional(),
});

export type CampaignUpdateInput = z.infer<typeof campaignUpdateInputSchema>;

export const campaignListResponseSchema = z.object({
	items: z.array(campaignSchema),
	total: z.number(),
	limit: z.number(),
	offset: z.number(),
});

export type CampaignListResponse = z.infer<typeof campaignListResponseSchema>;

// Lead Workbench Specific Types (Story 21.15 & SDR Pipeline)
export const leadPipelineStatusSchema = z.enum([
	"raw",
	"deduped",
	"scored",
	"enriched",
	"verified",
]);

export type LeadPipelineStatus = z.infer<typeof leadPipelineStatusSchema>;

export const sdrQualificationStatusSchema = z.enum([
	"qualified",
	"not_icp",
	"bad_contact",
	"already_customer",
	"unqualified",
]);

export type SdrQualificationStatus = z.infer<typeof sdrQualificationStatusSchema>;

export const fitFactorRationaleSchema = z.object({
	factor: z.string(),
	score: z.number(),
	weight: z.number(),
	matched: z.boolean(),
	detail: z.string(),
});

export type FitFactorRationale = z.infer<typeof fitFactorRationaleSchema>;

export const aiRationaleSchema = z.object({
	lead_id: z.string().uuid(),
	fit_rationale: z.string(),
	fit_factors: z.array(fitFactorRationaleSchema).default([]),
	intent_signals: z.array(z.string()).default([]),
	hiring_signals: z.array(z.string()).default([]),
	source_evidence: z.object({
		source: z.string(),
		source_url: z.string().nullable().optional(),
		posted_at: z.string().nullable().optional(),
		raw_snippet: z.string().nullable().optional(),
		matched_keywords: z.array(z.string()).default([]),
	}),
	suggested_icebreaker: z.string().nullable().optional(),
	confidence_score: z.number().min(0).max(1).default(0.85),
});

export type AiRationale = z.infer<typeof aiRationaleSchema>;

export const workbenchLeadSchema = leadSchema.extend({
	pipeline_stage: leadPipelineStatusSchema.default("scored"),
	sdr_status: sdrQualificationStatusSchema.nullable().optional(),
	qualification_note: z.string().nullable().optional(),
	ai_rationale: aiRationaleSchema.nullable().optional(),
	campaign_id: z.string().uuid().nullable().optional(),
});

export type WorkbenchLead = z.infer<typeof workbenchLeadSchema>;
