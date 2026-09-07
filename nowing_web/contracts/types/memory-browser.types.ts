import { z } from "zod";

export const memoryBrowserCreatorSchema = z.object({
  id: z.string(),
  email: z.string().nullable().optional(),
});

export const memoryBrowserListItemSchema = z.object({
  id: z.number(),
  content_snippet: z.string(),
  source_type: z.string(),
  source_url: z.string().nullable().optional(),
  confidence: z.number().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string().nullable().optional(),
  created_by: memoryBrowserCreatorSchema.nullable().optional(),
  version_count: z.number(),
  flag_status: z.string().nullable().optional(),
});

export const memoryBrowserListResponseSchema = z.object({
  items: z.array(memoryBrowserListItemSchema),
  total: z.number(),
  page: z.number(),
  page_size: z.number(),
});

export const memoryVersionReadSchema = z.object({
  previous_content: z.string(),
  corrected_content: z.string(),
  corrected_by: memoryBrowserCreatorSchema.nullable().optional(),
  created_at: z.string(),
});

export const memoryRelationReadSchema = z.object({
  relation_type: z.string(),
  to_memory_id: z.number(),
  weight: z.number().nullable().optional(),
});

export const researchThreadSummarySchema = z.object({
  id: z.number(),
  title: z.string(),
  memories: z.array(memoryBrowserListItemSchema),
});

export const memoryBrowserDetailCitationsSchema = z.object({
  source_type: z.string(),
  source_url: z.string().nullable().optional(),
  source_run_id: z.string().nullable().optional(),
  source_uuid: z.string().nullable().optional(),
  source_entity_type: z.string().nullable().optional(),
  source_id: z.number().nullable().optional(),
  source_capability: z.string().nullable().optional(),
  source_input: z.record(z.string(), z.unknown()).nullable().optional(),
});

export const memoryBrowserDetailResponseSchema = z.object({
  id: z.number(),
  workspace_id: z.number(),
  content: z.string(),
  source_type: z.string(),
  source_url: z.string().nullable().optional(),
  confidence: z.number().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string().nullable().optional(),
  created_by: memoryBrowserCreatorSchema.nullable().optional(),
  citations: memoryBrowserDetailCitationsSchema,
  versions: z.array(memoryVersionReadSchema),
  research_thread: researchThreadSummarySchema.nullable().optional(),
  relations: z.array(memoryRelationReadSchema),
});

export const memoryReviewQueueReadSchema = z.object({
  id: z.number(),
  memory_id: z.number(),
  workspace_id: z.number(),
  flag_reason: z.string(),
  flagged_by: z.string(),
  status: z.string(),
  created_at: z.string(),
});

export const memoryBrowserQuerySchema = z.object({
  page: z.number().int().min(1).optional(),
  page_size: z.number().int().min(1).max(100).optional(),
  source_types: z.string().optional(),
  confidence_min: z.number().min(0).max(1).optional(),
  confidence_max: z.number().min(0).max(1).optional(),
  created_after: z.string().datetime().optional(),
  created_before: z.string().datetime().optional(),
  created_by: z.string().uuid().optional(),
  keyword: z.string().optional(),
  sort: z.string().optional(),
  sort_dir: z.enum(["asc", "desc"]).optional(),
});

export type MemoryBrowserCreator = z.infer<typeof memoryBrowserCreatorSchema>;
export type MemoryBrowserListItem = z.infer<typeof memoryBrowserListItemSchema>;
export type MemoryBrowserListResponse = z.infer<typeof memoryBrowserListResponseSchema>;
export type MemoryVersionRead = z.infer<typeof memoryVersionReadSchema>;
export type MemoryRelationRead = z.infer<typeof memoryRelationReadSchema>;
export type ResearchThreadSummary = z.infer<typeof researchThreadSummarySchema>;
export type MemoryBrowserDetailCitations = z.infer<typeof memoryBrowserDetailCitationsSchema>;
export type MemoryBrowserDetailResponse = z.infer<typeof memoryBrowserDetailResponseSchema>;
export type MemoryReviewQueueRead = z.infer<typeof memoryReviewQueueReadSchema>;
export type MemoryBrowserQuery = z.infer<typeof memoryBrowserQuerySchema>;
