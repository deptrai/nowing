import { z } from "zod";

export const adminGlobalConnectionSourceEnum = z.enum(["managed", "file", "config"]);
export const adminGlobalModelSourceEnum = adminGlobalConnectionSourceEnum;

export const adminGlobalConnectionScopeEnum = z.enum(["GLOBAL"]);

export const adminGlobalModelPricing = z.object({
	cost_per_1k_input_tokens: z.number().nullable().optional(),
	cost_per_1k_output_tokens: z.number().nullable().optional(),
	rpm: z.number().int().nullable().optional(),
	tpm: z.number().int().nullable().optional(),
	quality_score: z.number().int().nullable().optional(),
	auto_pin_tier: z.string().nullable().optional(),
	router_pool_eligible: z.boolean().default(true),
});

export const adminGlobalModelSelection = z.object({
	model_id: z.string().min(1),
	display_name: z.string().nullable().optional(),
	supports_chat: z.boolean().default(true),
	max_input_tokens: z.number().int().nullable().optional(),
	supports_image_input: z.boolean().nullable().optional(),
	supports_tools: z.boolean().nullable().optional(),
	supports_image_generation: z.boolean().nullable().optional(),
	enabled: z.boolean().default(true),
	metadata: z.record(z.string(), z.any()).default({}),
	billing_tier: z.string().nullable().optional(),
	base_model: z.string().nullable().optional(),
	pricing: adminGlobalModelPricing.default({ router_pool_eligible: true }),
});

export const adminGlobalConnectionCreateRequest = z.object({
	provider: z.string().min(1),
	base_url: z.string().nullable().optional(),
	api_key: z.string().nullable().optional(),
	extra: z.record(z.string(), z.any()).default({}),
	enabled: z.boolean().default(true),
	models: z.array(adminGlobalModelSelection).min(1),
});

export const adminGlobalConnectionUpdateRequest = z.object({
	provider: z.string().nullable().optional(),
	base_url: z.string().nullable().optional(),
	api_key: z.string().nullable().optional(),
	extra: z.record(z.string(), z.any()).optional(),
	enabled: z.boolean().optional(),
});

export const adminGlobalModelUpdateRequest = z.object({
	display_name: z.string().nullable().optional(),
	enabled: z.boolean().optional(),
	supports_chat: z.boolean().nullable().optional(),
	max_input_tokens: z.number().int().nullable().optional(),
	supports_image_input: z.boolean().nullable().optional(),
	supports_tools: z.boolean().nullable().optional(),
	supports_image_generation: z.boolean().nullable().optional(),
	capabilities_override: z.record(z.string(), z.any()).optional(),
	billing_tier: z.string().nullable().optional(),
	base_model: z.string().nullable().optional(),
	pricing: adminGlobalModelPricing.optional(),
});

export const adminGlobalModelsBulkUpdateRequest = z.object({
	model_ids: z.array(z.number().int()).min(1).max(1000),
	enabled: z.boolean(),
});

export const adminGlobalModelTestRequest = z.object({
	model_id: z.string().min(1),
});

export const adminGlobalModelTestPreviewRequest = adminGlobalConnectionCreateRequest.extend({
	model_id: z.string().min(1),
});

export const adminGlobalModelRead = z.object({
	id: z.number(),
	connection_id: z.number(),
	model_id: z.string(),
	display_name: z.string().nullable().optional(),
	source: adminGlobalModelSourceEnum,
	can_edit: z.boolean(),
	can_delete: z.boolean(),
	supports_chat: z.boolean().nullable().optional(),
	max_input_tokens: z.number().int().nullable().optional(),
	supports_image_input: z.boolean().nullable().optional(),
	supports_tools: z.boolean().nullable().optional(),
	supports_image_generation: z.boolean().nullable().optional(),
	capabilities_override: z.record(z.string(), z.any()).default({}),
	enabled: z.boolean(),
	billing_tier: z.string().nullable().optional(),
	base_model: z.string().nullable().optional(),
	catalog: z.record(z.string(), z.any()).default({}),
	cost_per_1k_input_tokens: z.number().nullable().optional(),
	cost_per_1k_output_tokens: z.number().nullable().optional(),
	rpm: z.number().int().nullable().optional(),
	tpm: z.number().int().nullable().optional(),
	quality_score: z.number().int().nullable().optional(),
	auto_pin_tier: z.string().nullable().optional(),
	created_at: z.string().nullable().optional(),
});

export const adminGlobalModelPreviewRead = adminGlobalModelRead.extend({
	id: z.number().nullable().optional(),
});

export const adminGlobalConnectionRead = z.object({
	id: z.number(),
	provider: z.string(),
	base_url: z.string().nullable().optional(),
	api_key: z.null(),
	extra: z.record(z.string(), z.any()).default({}),
	scope: adminGlobalConnectionScopeEnum,
	workspace_id: z.number().nullable().optional(),
	user_id: z.string().nullable().optional(),
	enabled: z.boolean(),
	has_api_key: z.boolean(),
	source: adminGlobalConnectionSourceEnum,
	can_edit: z.boolean(),
	can_delete: z.boolean(),
	models: z.array(adminGlobalModelRead).default([]),
	created_at: z.string().nullable().optional(),
});

export const adminGlobalConnectionListResponse = z.array(adminGlobalConnectionRead);
export const adminGlobalModelListResponse = z.array(adminGlobalModelRead);
export const adminGlobalModelPreviewListResponse = z.array(adminGlobalModelPreviewRead);

export type AdminGlobalConnectionSource = z.infer<typeof adminGlobalConnectionSourceEnum>;
export type AdminGlobalModelSource = z.infer<typeof adminGlobalModelSourceEnum>;
export type AdminGlobalConnectionScope = z.infer<typeof adminGlobalConnectionScopeEnum>;
export type AdminGlobalModelPricing = z.infer<typeof adminGlobalModelPricing>;
export type AdminGlobalModelSelection = z.infer<typeof adminGlobalModelSelection>;
export type AdminGlobalConnectionCreateRequest = z.infer<typeof adminGlobalConnectionCreateRequest>;
export type AdminGlobalConnectionUpdateRequest = z.infer<typeof adminGlobalConnectionUpdateRequest>;
export type AdminGlobalModelUpdateRequest = z.infer<typeof adminGlobalModelUpdateRequest>;
export type AdminGlobalModelsBulkUpdateRequest = z.infer<typeof adminGlobalModelsBulkUpdateRequest>;
export type AdminGlobalModelTestRequest = z.infer<typeof adminGlobalModelTestRequest>;
export type AdminGlobalModelTestPreviewRequest = z.infer<typeof adminGlobalModelTestPreviewRequest>;
export type AdminGlobalModelRead = z.infer<typeof adminGlobalModelRead>;
export type AdminGlobalModelPreviewRead = z.infer<typeof adminGlobalModelPreviewRead>;
export type AdminGlobalConnectionRead = z.infer<typeof adminGlobalConnectionRead>;
