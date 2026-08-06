import { z } from "zod";
import { automation, automationDefinition } from "./automation.types";

export const playbookScope = z.enum(["workspace", "system"]);
export type PlaybookScope = z.infer<typeof playbookScope>;

export const playbookCreateRequest = z.object({
	source_automation_id: z.number(),
	name: z.string().min(1).max(200),
	description: z.string().nullable().optional(),
	tool_scope: z.array(z.string()).default([]),
	verticals: z.array(z.string()).default([]),
});
export type PlaybookCreateRequest = z.infer<typeof playbookCreateRequest>;

export const playbookUpdateRequest = z.object({
	name: z.string().min(1).max(200).nullable().optional(),
	description: z.string().nullable().optional(),
	definition: automationDefinition.nullable().optional(),
	tool_scope: z.array(z.string()).nullable().optional(),
	verticals: z.array(z.string()).nullable().optional(),
});
export type PlaybookUpdateRequest = z.infer<typeof playbookUpdateRequest>;

export const playbookInstantiateRequest = z.object({
	workspace_id: z.number(),
	inputs: z.record(z.string(), z.any()).default({}),
	name: z.string().min(1).max(200).nullable().optional(),
	description: z.string().nullable().optional(),
});
export type PlaybookInstantiateRequest = z.infer<typeof playbookInstantiateRequest>;

export const playbookSummary = z.object({
	id: z.number(),
	workspace_id: z.number().nullable(),
	name: z.string(),
	description: z.string().nullable().optional(),
	version: z.number(),
	scope: playbookScope,
	verticals: z.array(z.string()),
	created_at: z.string(),
	updated_at: z.string(),
});
export type PlaybookSummary = z.infer<typeof playbookSummary>;

export const playbookDetail = playbookSummary.extend({
	definition: automationDefinition,
	inputs_schema: z.record(z.string(), z.any()),
	tool_scope: z.array(z.string()),
	source_automation_id: z.number().nullable().optional(),
});
export type PlaybookDetail = z.infer<typeof playbookDetail>;

export const playbookListResponse = z.object({
	items: z.array(playbookSummary),
	total: z.number(),
});
export type PlaybookListResponse = z.infer<typeof playbookListResponse>;

export const playbookListParams = z.object({
	workspace_id: z.number(),
	limit: z.number().int().min(1).max(200).default(50),
	offset: z.number().int().min(0).default(0),
});
export type PlaybookListParams = z.infer<typeof playbookListParams>;

export const playbookInstantiateResponse = automation;
export type PlaybookInstantiateResponse = z.infer<typeof playbookInstantiateResponse>;
