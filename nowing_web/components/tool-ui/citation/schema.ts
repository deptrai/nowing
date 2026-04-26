import { z } from "zod";
import { ToolUIIdSchema, ToolUIReceiptSchema, ToolUIRoleSchema } from "../shared/schema";

export const CitationTypeSchema = z.enum([
	"webpage",
	"document",
	"article",
	"api",
	"code",
	"other",
]);

export type CitationType = z.infer<typeof CitationTypeSchema>;

export const CitationVariantSchema = z.enum([
	"default",
	"inline",
	"stacked",
	"cluster",
	"conflict",
]);

export type CitationVariant = z.infer<typeof CitationVariantSchema>;

export const SerializableCitationSchema = z.object({
	id: ToolUIIdSchema,
	role: ToolUIRoleSchema.optional(),
	receipt: ToolUIReceiptSchema.optional(),
	href: z.string().url(),
	title: z.string(),
	snippet: z.string().optional(),
	domain: z.string().optional(),
	favicon: z.string().url().optional(),
	author: z.string().optional(),
	publishedAt: z.string().datetime().optional(),
	type: CitationTypeSchema.optional(),
	locale: z.string().optional(),
});

export type SerializableCitation = z.infer<typeof SerializableCitationSchema>;

// ─── P7 / AC8 — FE-side conflict detection (no backend coupling) ─────────────

/** Numeric delta threshold for flagging conflicts between sources (5%). Tunable. */
export const CONFLICT_NUMERIC_DELTA = 0.05;

/**
 * Detect whether a set of claimed values across multiple sources conflict.
 *
 * - Numeric values: conflict if (max - min) / |max| exceeds CONFLICT_NUMERIC_DELTA.
 * - Categorical (string/boolean) values: conflict on exact inequality.
 * - Mixed or empty input: no conflict.
 *
 * Pure function — safe for render-time use.
 */
// ─── CryptoDataCitation (9-UX-2) ─────────────────────────────────────────────

export interface CryptoDataSource {
	provider: string;
	favicon?: string;
	fetchedAt: string;
	rawValue?: string | number;
	rawUrl?: string;
}

export interface CryptoDataCitation {
	id: string;
	value: string;
	sources: CryptoDataSource[];
	conflict?: boolean;
	agentAttribution?: string;
	confidence?: number;
	stalenessMs?: number;
}

export type CryptoDataCitationMap = ReadonlyMap<string, CryptoDataCitation>;

export function detectConflict(values: readonly (number | string | boolean)[]): boolean {
	if (values.length < 2) return false;
	const first = values[0];
	if (typeof first === "number") {
		if (!values.every((v) => typeof v === "number" && Number.isFinite(v))) return false;
		const nums = values as readonly number[];
		const max = Math.max(...nums);
		const min = Math.min(...nums);
		const denom = Math.abs(max);
		if (denom === 0) return min !== 0;
		return (max - min) / denom > CONFLICT_NUMERIC_DELTA;
	}
	return values.some((v) => v !== first);
}
