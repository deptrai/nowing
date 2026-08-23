import { z } from "zod";
import { paginationQueryParams } from ".";
import { llmSetupStatus } from "./model-connections.types";

export const workspaceVertical = z.enum(["general", "real_estate", "auto", "b2b_equipment"]);
export type WorkspaceVertical = z.infer<typeof workspaceVertical>;

export const workspace = z.object({
	id: z.number(),
	name: z.string(),
	description: z.string().nullable(),
	vertical: workspaceVertical.default("general"),
	created_at: z.string(),
	user_id: z.string(),
	citations_enabled: z.boolean(),
	api_access_enabled: z.boolean().optional().default(false),
	qna_custom_instructions: z.string().nullable(),
	document_retention_days: z.number().nullable().optional(),
	auto_archive_enabled: z.boolean().optional().default(false),
	document_retention_action: z.string().optional().default("archive"),
	memory_auto_extract_enabled: z.boolean().optional().default(true),
	auto_reply_enabled: z.boolean().optional(),
	auto_reply_collections: z.array(z.number()).optional().default([]),
	auto_reply_fallback: z.string().nullable().optional(),
	auto_reply_recipient_chat_id: z.string().nullable().optional(),
	member_count: z.number(),
	is_owner: z.boolean(),
});

/**
 * Get workspaces
 */
export const getWorkspacesRequest = z.object({
	queryParams: paginationQueryParams
		.extend({
			owned_only: z.boolean().optional(),
		})
		.nullish(),
});

export const getWorkspacesResponse = z.array(workspace);

/**
 * Create workspace
 */
export const createWorkspaceRequest = workspace
	.pick({ name: true, description: true, vertical: true })
	.extend({
		citations_enabled: z.boolean().prefault(true).optional(),
		qna_custom_instructions: z.string().nullable().optional(),
	});

export const createWorkspaceResponse = workspace
	.omit({ member_count: true, is_owner: true })
	.extend({ llm_setup: llmSetupStatus.nullable().optional() });

/**
 * Get workspace
 */
export const getWorkspaceRequest = workspace.pick({ id: true });

export const getWorkspaceResponse = workspace.omit({ member_count: true });

/**
 * Update workspace
 */
export const updateWorkspaceRequest = z.object({
	id: z.number(),
	data: workspace
		.pick({
			name: true,
			description: true,
			vertical: true,
			citations_enabled: true,
			api_access_enabled: true,
			qna_custom_instructions: true,
			document_retention_days: true,
			auto_archive_enabled: true,
			document_retention_action: true,
			memory_auto_extract_enabled: true,
			auto_reply_enabled: true,
			auto_reply_collections: true,
			auto_reply_fallback: true,
			auto_reply_recipient_chat_id: true,
		})
		.partial(),
});

export const updateWorkspaceResponse = workspace.omit({ member_count: true });

export const updateWorkspaceApiAccessRequest = z.object({
	id: z.number(),
	api_access_enabled: z.boolean(),
});

export const updateWorkspaceApiAccessResponse = workspace.omit({
	member_count: true,
	is_owner: true,
});

/**
 * Delete workspace
 */
export const deleteWorkspaceRequest = workspace.pick({ id: true });

export const deleteWorkspaceResponse = z.object({
	message: z.literal("Workspace deleted successfully"),
});

/**
 * Leave workspace (for non-owners)
 */
export const leaveWorkspaceResponse = z.object({
	message: z.literal("Successfully left the workspace"),
});

export const workspaceMcpTool = z.object({
	name: z.string(),
	enabled: z.boolean(),
	is_system: z.boolean(),
	group: z.string(),
});

export const getWorkspaceMcpToolsResponse = z.array(workspaceMcpTool);

export const updateWorkspaceMcpToolRequest = z.object({
	id: z.number(),
	tool_name: z.string(),
	enabled: z.boolean(),
});

export const updateWorkspaceMcpToolResponse = workspaceMcpTool;

/**
 * Workspace limits
 */
export const workspaceLimitUsage = z.object({
	documents: z.number(),
	members: z.number(),
	runs: z.number(),
	storage_bytes: z.number(),
});

export const autoExtractUsage = z.object({
	period_spend_micros: z.number(),
	period_count: z.number(),
	period_window_hours: z.number(),
});

export const getWorkspaceLimitsResponse = z.object({
	plan_tier: z.string().nullable(),
	max_documents: z.number().nullable(),
	max_members: z.number().nullable(),
	max_runs: z.number().nullable(),
	max_storage_bytes: z.number().nullable(),
	run_period_hours: z.number(),
	auto_extract_item_cap: z.number().nullable().optional(),
	auto_extract_spend_cap_micros: z.number().nullable().optional(),
	auto_extract_wallet_pre_check: z.boolean().nullable().optional(),
	auto_extract_usage: autoExtractUsage,
	usage: workspaceLimitUsage,
});

export const updateWorkspaceLimitsRequest = z.object({
	id: z.number(),
	auto_extract_item_cap: z.number().nullable().optional(),
	auto_extract_spend_cap_micros: z.number().nullable().optional(),
	auto_extract_wallet_pre_check: z.boolean().nullable().optional(),
});

// Inferred types
export type Workspace = z.infer<typeof workspace>;
export type WorkspaceMcpTool = z.infer<typeof workspaceMcpTool>;
export type GetWorkspaceMcpToolsResponse = z.infer<typeof getWorkspaceMcpToolsResponse>;
export type UpdateWorkspaceMcpToolRequest = z.infer<typeof updateWorkspaceMcpToolRequest>;
export type UpdateWorkspaceMcpToolResponse = z.infer<typeof updateWorkspaceMcpToolResponse>;
export type GetWorkspacesRequest = z.infer<typeof getWorkspacesRequest>;
export type GetWorkspacesResponse = z.infer<typeof getWorkspacesResponse>;
export type CreateWorkspaceRequest = z.infer<typeof createWorkspaceRequest>;
export type CreateWorkspaceResponse = z.infer<typeof createWorkspaceResponse>;
export type GetWorkspaceRequest = z.infer<typeof getWorkspaceRequest>;
export type GetWorkspaceResponse = z.infer<typeof getWorkspaceResponse>;
export type UpdateWorkspaceRequest = z.infer<typeof updateWorkspaceRequest>;
export type UpdateWorkspaceResponse = z.infer<typeof updateWorkspaceResponse>;
export type UpdateWorkspaceApiAccessRequest = z.infer<typeof updateWorkspaceApiAccessRequest>;
export type UpdateWorkspaceApiAccessResponse = z.infer<typeof updateWorkspaceApiAccessResponse>;
export type DeleteWorkspaceRequest = z.infer<typeof deleteWorkspaceRequest>;
export type DeleteWorkspaceResponse = z.infer<typeof deleteWorkspaceResponse>;
export type WorkspaceLimitUsage = z.infer<typeof workspaceLimitUsage>;
export type GetWorkspaceLimitsResponse = z.infer<typeof getWorkspaceLimitsResponse>;
export type UpdateWorkspaceLimitsRequest = z.infer<typeof updateWorkspaceLimitsRequest>;
