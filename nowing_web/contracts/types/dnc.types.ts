import { z } from "zod";

export const dncRecordTypeSchema = z.enum(["phone", "email", "domain", "tax_id"]);
export type DncRecordType = z.infer<typeof dncRecordTypeSchema>;

export const dncRecordSchema = z.object({
	id: z.string(),
	workspace_id: z.number(),
	record_type: z.string(),
	value: z.string().nullable().optional(),
	value_hmac: z.string(),
	reason: z.string().nullable().optional(),
	source: z.string(),
	created_at: z.string(),
	updated_at: z.string(),
});
export type DncRecord = z.infer<typeof dncRecordSchema>;

export const dncListResponseSchema = z.object({
	records: z.array(dncRecordSchema),
	total_count: z.number(),
	page: z.number(),
	page_size: z.number(),
});
export type DncListResponse = z.infer<typeof dncListResponseSchema>;

export const dncRecordCreateSchema = z.object({
	record_type: dncRecordTypeSchema,
	value: z.string().min(1),
	reason: z.string().optional().default("Opt-out requested"),
});
export type DncRecordCreate = z.infer<typeof dncRecordCreateSchema>;

export const dncCsvImportResponseSchema = z.object({
	imported_count: z.number(),
	skipped_count: z.number(),
	failed_count: z.number(),
	errors: z.array(z.string()),
});
export type DncCsvImportResponse = z.infer<typeof dncCsvImportResponseSchema>;

export const piiPurgeResponseSchema = z.object({
	status: z.string(),
	lead_id: z.string(),
	purged_at: z.string(),
	dnc_appended: z.boolean(),
});
export type PiiPurgeResponse = z.infer<typeof piiPurgeResponseSchema>;
