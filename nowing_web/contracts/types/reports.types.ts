import { z } from "zod";

// =============================================================================
// Reports — mirror app/schemas/reports.py ReportRead (list view, no content).
// Resumes are reports with content_type === "typst".
// =============================================================================

export const reportMetadata = z
	.object({
		status: z.enum(["ready", "failed"]).nullish(),
		word_count: z.number().nullish(),
	})
	.nullish();

export const reportListItem = z.object({
	id: z.number(),
	title: z.string(),
	content_type: z.string().default("markdown"),
	report_metadata: reportMetadata,
	thread_id: z.number().nullish(),
	created_at: z.string(),
});
export type ReportListItem = z.infer<typeof reportListItem>;

export const reportList = z.array(reportListItem);

// =============================================================================
// Story 6.12: Narrative Reports contracts
// =============================================================================

export const sourceCitation = z.object({
	source_id: z.string(),
	title: z.string(),
	url: z.string(),
	pub_date: z.string().nullish(),
	source_type: z.string().default("web"),
});

export const narrativeTemplateParameter = z.object({
	name: z.string(),
	label: z.string(),
	description: z.string().nullish(),
	type: z.string().default("string"),
	required: z.boolean().default(true),
	default: z.unknown().optional(),
	options: z.array(z.object({ value: z.string(), label: z.string() })).nullish(),
});

export const narrativeTemplate = z.object({
	template_id: z.string(),
	name: z.string(),
	description: z.string(),
	narrative_style: z.string(),
	required_capability: z.string(),
	parameters: z.array(narrativeTemplateParameter),
});

export const narrativeTemplateList = z.array(narrativeTemplate);

export const narrativeReportCreateRequest = z.object({
	template_id: z.string(),
	title: z.string().nullish(),
	parameters: z.record(z.string(), z.unknown()),
});

export const reportContentRead = z.object({
	id: z.number(),
	title: z.string(),
	content: z.string().nullish(),
	content_type: z.string().default("markdown"),
	report_metadata: z.record(z.string(), z.unknown()).nullish(),
	report_group_id: z.number().nullish(),
	versions: z.array(z.object({ id: z.number(), created_at: z.string() })).default([]),
});

export type SourceCitation = z.infer<typeof sourceCitation>;
export type NarrativeTemplate = z.infer<typeof narrativeTemplate>;
export type NarrativeTemplateList = z.infer<typeof narrativeTemplateList>;
export type NarrativeReportCreateRequest = z.infer<typeof narrativeReportCreateRequest>;
export type ReportContentRead = z.infer<typeof reportContentRead>;
