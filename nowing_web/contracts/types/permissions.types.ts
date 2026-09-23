import { z } from "zod";

export const CANONICAL_PERMISSIONS = {
	ANALYTICS_READ: "analytics:read",
	BILLING_READ: "billing:read",
	BILLING_MANAGE: "billing:manage",
	SOURCE_CONFIGURE: "source:configure",
	TOOLS_ENABLE: "tools:enable",
	MEMORY_READ: "memory:read",
	MEMORY_CREATE: "memory:create",
	MEMORY_UPDATE: "memory:update",
	MEMORY_DELETE: "memory:delete",
	SETTINGS_VIEW: "settings:view",
	SETTINGS_UPDATE: "settings:update",
	SETTINGS_DELETE: "settings:delete",
	MEMBERS_INVITE: "members:invite",
	MEMBERS_VIEW: "members:view",
	MEMBERS_REMOVE: "members:remove",
	MEMBERS_MANAGE_ROLES: "members:manage_roles",
	DOCUMENTS_CREATE: "documents:create",
	DOCUMENTS_READ: "documents:read",
	DOCUMENTS_UPDATE: "documents:update",
	DOCUMENTS_DELETE: "documents:delete",
	CHATS_CREATE: "chats:create",
	CHATS_READ: "chats:read",
	CHATS_UPDATE: "chats:update",
	CHATS_DELETE: "chats:delete",
	COMMENTS_CREATE: "comments:create",
	COMMENTS_READ: "comments:read",
	COMMENTS_DELETE: "comments:delete",
	LLM_CONFIGS_CREATE: "llm_configs:create",
	LLM_CONFIGS_READ: "llm_configs:read",
	LLM_CONFIGS_UPDATE: "llm_configs:update",
	LLM_CONFIGS_DELETE: "llm_configs:delete",
	PODCASTS_CREATE: "podcasts:create",
	PODCASTS_READ: "podcasts:read",
	PODCASTS_UPDATE: "podcasts:update",
	PODCASTS_DELETE: "podcasts:delete",
	AUTOMATIONS_CREATE: "automations:create",
	AUTOMATIONS_READ: "automations:read",
	AUTOMATIONS_UPDATE: "automations:update",
	AUTOMATIONS_DELETE: "automations:delete",
	AUTOMATIONS_EXECUTE: "automations:execute",
	CONNECTORS_CREATE: "connectors:create",
	CONNECTORS_READ: "connectors:read",
	CONNECTORS_UPDATE: "connectors:update",
	CONNECTORS_DELETE: "connectors:delete",
	LOGS_READ: "logs:read",
	LOGS_DELETE: "logs:delete",
	ROLES_CREATE: "roles:create",
	ROLES_READ: "roles:read",
	ROLES_UPDATE: "roles:update",
	ROLES_DELETE: "roles:delete",
} as const;

export type CanonicalPermission =
	(typeof CANONICAL_PERMISSIONS)[keyof typeof CANONICAL_PERMISSIONS];

export const permissionInfo = z.object({
	value: z.string(),
	name: z.string(),
	category: z.string(),
	description: z.string(),
});

/**
 * Get permissions
 */
export const getPermissionsResponse = z.object({
	permissions: z.array(permissionInfo),
});

export type PermissionInfo = z.infer<typeof permissionInfo>;
export type GetPermissionsResponse = z.infer<typeof getPermissionsResponse>;
