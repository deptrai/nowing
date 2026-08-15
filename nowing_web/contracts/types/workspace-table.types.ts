import { z } from "zod";

export const workspaceTableSchema = z.object({
	id: z.string().uuid(),
	workspace_id: z.number(),
	name: z.string().min(1).max(200),
	icon: z.string().default("table"),
	filter_preset: z.record(z.string(), z.unknown()).default({}),
	columns_config: z.record(z.string(), z.unknown()).default({}),
	created_at: z.string(),
	updated_at: z.string().nullable().optional(),
});

export type WorkspaceTable = z.infer<typeof workspaceTableSchema>;

export const workspaceTableCreateSchema = z.object({
	name: z.string().min(1).max(200),
	icon: z.string().default("table"),
	filter_preset: z.record(z.string(), z.unknown()).optional(),
	columns_config: z.record(z.string(), z.unknown()).optional(),
});

export type WorkspaceTableCreate = z.infer<typeof workspaceTableCreateSchema>;

export const workspaceTableUpdateSchema = z.object({
	name: z.string().min(1).max(200).optional(),
	icon: z.string().optional(),
	filter_preset: z.record(z.string(), z.unknown()).optional(),
	columns_config: z.record(z.string(), z.unknown()).optional(),
});

export type WorkspaceTableUpdate = z.infer<typeof workspaceTableUpdateSchema>;

export const exportJobResponseSchema = z.object({
	job_id: z.string().uuid(),
	status: z.string(),
	export_type: z.string(),
	total_rows: z.number(),
	processed_rows: z.number(),
	target_url: z.string().nullable().optional(),
	error_message: z.string().nullable().optional(),
	created_at: z.string(),
});

export type ExportJobResponse = z.infer<typeof exportJobResponseSchema>;

export interface ExportRequestPayload {
	export_type: "csv" | "lark_base" | "google_sheets" | "share_link";
	table_id?: string | null;
	lead_ids?: string[];
	mask_pii?: boolean;
	target_config?: Record<string, unknown>;
}
