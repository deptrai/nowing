import { z } from "zod";

export const adminAgentConfigRead = z.object({
	id: z.string().uuid(),
	client_id: z.string(),
	name: z.string(),
	display_name: z.string(),
	slug: z.string(),
	system_instructions: z.string().nullable().optional(),
	enabled_tools: z.array(z.string()).default([]),
	disabled_tools: z.array(z.string()).default([]),
	model_name: z.string().nullable().optional(),
	citations_enabled: z.boolean(),
	is_active: z.boolean(),
	created_at: z.string().nullable().optional(),
	updated_at: z.string().nullable().optional(),
});

export const adminAgentConfigListResponse = z.array(adminAgentConfigRead);

export const adminAgentConfigCreateRequest = z.object({
	client_id: z.string().min(1),
	name: z.string().min(1).max(256),
	display_name: z.string().min(1).max(256),
	slug: z.string().min(1).max(64),
	system_instructions: z.string().max(100000).nullable().optional(),
	enabled_tools: z.array(z.string()).default([]),
	disabled_tools: z.array(z.string()).default([]),
	model_name: z.string().max(256).nullable().optional(),
	citations_enabled: z.boolean().default(true),
	is_active: z.boolean().default(true),
});

export const adminAgentConfigUpdateRequest = z.object({
	name: z.string().min(1).max(256).optional(),
	display_name: z.string().min(1).max(256).optional(),
	slug: z.string().min(1).max(64).optional(),
	system_instructions: z.string().max(100000).nullable().optional(),
	enabled_tools: z.array(z.string()).optional(),
	disabled_tools: z.array(z.string()).optional(),
	model_name: z.string().max(256).nullable().optional(),
	citations_enabled: z.boolean().optional(),
	is_active: z.boolean().optional(),
});

export type AdminAgentConfigRead = z.infer<typeof adminAgentConfigRead>;
export type AdminAgentConfigCreateRequest = z.infer<typeof adminAgentConfigCreateRequest>;
export type AdminAgentConfigUpdateRequest = z.infer<typeof adminAgentConfigUpdateRequest>;
