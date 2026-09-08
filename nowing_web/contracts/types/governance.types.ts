import { z } from "zod";

// ------------------------------------------------------------------
// Source risk tiers
// ------------------------------------------------------------------

export const riskTierSchema = z.enum(["low", "medium", "high"]);
export type RiskTier = z.infer<typeof riskTierSchema>;

export const sourceRiskTierSchema = z.object({
	source_type: z.string(),
	risk_tier: riskTierSchema,
	recommended_retention_days: z.number().nullable().optional(),
	notes: z.string().nullable().optional(),
});
export type SourceRiskTier = z.infer<typeof sourceRiskTierSchema>;

export const sourceRiskTierUpdateSchema = z.object({
	source_type: z.string(),
	risk_tier: riskTierSchema,
	recommended_retention_days: z.number().int().min(1).max(36500).nullable().optional(),
	notes: z.string().max(2000).nullable().optional(),
});
export type SourceRiskTierUpdate = z.infer<typeof sourceRiskTierUpdateSchema>;

// ------------------------------------------------------------------
// Retention policy
// ------------------------------------------------------------------

export const retentionActionSchema = z.enum(["archive", "delete"]);
export type RetentionAction = z.infer<typeof retentionActionSchema>;

export const retentionPolicySchema = z.object({
	document_retention_days: z.number().nullable().optional(),
	auto_archive_enabled: z.boolean().default(false),
	document_retention_action: retentionActionSchema.default("archive"),
	memory_retention_days: z.number().nullable().optional(),
	memory_auto_archive_enabled: z.boolean().default(false),
	memory_retention_action: retentionActionSchema.default("archive"),
});
export type RetentionPolicy = z.infer<typeof retentionPolicySchema>;

export const retentionPolicyUpdateSchema = z.object({
	document_retention_days: z.number().int().min(1).max(36500).nullable().optional(),
	auto_archive_enabled: z.boolean().nullable().optional(),
	document_retention_action: retentionActionSchema.nullable().optional(),
	memory_retention_days: z.number().int().min(1).max(36500).nullable().optional(),
	memory_auto_archive_enabled: z.boolean().nullable().optional(),
	memory_retention_action: retentionActionSchema.nullable().optional(),
});
export type RetentionPolicyUpdate = z.infer<typeof retentionPolicyUpdateSchema>;

// ------------------------------------------------------------------
// DNC records
// ------------------------------------------------------------------

export const dncRecordTypeSchema = z.enum(["phone", "email", "domain", "tax_id"]);
export type DncRecordType = z.infer<typeof dncRecordTypeSchema>;

export const governanceDncRecordSchema = z.object({
	id: z.string().uuid(),
	record_type: z.string(),
	value: z.string().nullable().optional(),
	value_masked: z.string().nullable().optional(),
	value_hmac: z.string(),
	reason: z.string().nullable().optional(),
	source: z.string(),
	created_at: z.string(),
	updated_at: z.string(),
	superseded_by_global: z.boolean().default(false),
});
export type GovernanceDncRecord = z.infer<typeof governanceDncRecordSchema>;

export const governanceDncRecordCreateSchema = z.object({
	record_type: dncRecordTypeSchema,
	value: z.string().min(1).max(255),
	reason: z.string().max(255).optional(),
});
export type GovernanceDncRecordCreate = z.infer<typeof governanceDncRecordCreateSchema>;

// ------------------------------------------------------------------
// Right-to-delete
// ------------------------------------------------------------------

export const rightToDeleteTypeSchema = z.enum(["single_memory", "bulk"]);
export type RightToDeleteType = z.infer<typeof rightToDeleteTypeSchema>;

export const memorySourceTypeSchema = z.enum([
	"document",
	"chat_message",
	"scraper_run",
	"manual",
	"unknown",
	"signal",
	"lead",
	"lead_score",
	"enrichment",
	"crm_connection",
	"crm_sync",
	"sequence_event",
	"outcome_event",
]);
export type MemorySourceType = z.infer<typeof memorySourceTypeSchema>;

export const rightToDeleteRequestSchema = z.object({
	type: rightToDeleteTypeSchema,
	memory_id: z.number().int().nullable().optional(),
	source_type: memorySourceTypeSchema.nullable().optional(),
	source_id: z.number().int().nullable().optional(),
	source_entity_type: z.string().nullable().optional(),
	created_before: z.string().datetime().nullable().optional(),
	created_after: z.string().datetime().nullable().optional(),
	dry_run: z.boolean().default(false),
	reason: z.string().min(1).max(500),
});
export type RightToDeleteRequest = z.infer<typeof rightToDeleteRequestSchema>;

export const rightToDeleteResponseSchema = z.object({
	dry_run: z.boolean(),
	affected_count: z.number(),
	preview_memory_ids: z.array(z.number()).default([]),
	job_id: z.string().nullable().optional(),
	status: z.string().nullable().optional(),
});
export type RightToDeleteResponse = z.infer<typeof rightToDeleteResponseSchema>;

// ------------------------------------------------------------------
// Audit log
// ------------------------------------------------------------------

export const auditLogFilterSchema = z.object({
	action_prefix: z.string().nullable().optional(),
	created_after: z.string().datetime().nullable().optional(),
	created_before: z.string().datetime().nullable().optional(),
	page: z.number().int().min(1).default(1),
	page_size: z.number().int().min(1).max(100).default(50),
});
export type AuditLogFilter = z.infer<typeof auditLogFilterSchema>;

export const auditLogEntrySchema = z.object({
	id: z.number(),
	action: z.string(),
	actor_id: z.string().uuid().nullable(),
	subject_id: z.string().uuid().nullable(),
	diff_payload: z.record(z.string(), z.any()).nullable().optional(),
	created_at: z.string(),
});
export type AuditLogEntry = z.infer<typeof auditLogEntrySchema>;

// ------------------------------------------------------------------
// Workspace lifecycle
// ------------------------------------------------------------------

export const workspaceStatusSchema = z.object({
	archived_at: z.string().nullable(),
	can_restore: z.boolean(),
	scrape_paused_at: z.string().nullable().optional(),
});
export type WorkspaceStatus = z.infer<typeof workspaceStatusSchema>;

// ------------------------------------------------------------------
// Overview
// ------------------------------------------------------------------

export const governanceOverviewSchema = z.object({
	retention_policy: retentionPolicySchema,
	source_risk_tiers: z.array(sourceRiskTierSchema).default([]),
	dnc_records: z.array(governanceDncRecordSchema).default([]),
	workspace_status: workspaceStatusSchema,
	deployment_mode: z.string().default("cloud"),
});
export type GovernanceOverview = z.infer<typeof governanceOverviewSchema>;
