import { z } from "zod";

export const actionCatalogItem = z.object({
	type: z.string(),
	name: z.string(),
	description: z.string(),
	params_schema: z.record(z.string(), z.any()),
	verticals: z.array(z.string()),
	business_name: z.string().nullable().optional(),
});

export type ActionCatalogItem = z.infer<typeof actionCatalogItem>;

export const actionCatalog = z.array(actionCatalogItem);

export type ActionCatalog = z.infer<typeof actionCatalog>;
