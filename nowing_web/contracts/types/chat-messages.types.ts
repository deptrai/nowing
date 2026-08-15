import { z } from "zod";

/**
 * Raw message from database (real-time sync).
 *
 * ``turn_id`` is included so consumers (e.g. ``convertToThreadMessage``)
 * can populate ``metadata.custom.chatTurnId`` on the
 * ``ThreadMessageLike`` even after the live-collab Zero re-sync. The
 * inline Revert button's ``(chat_turn_id, tool_name, position)``
 * fallback in tool-fallback.tsx depends on it.
 */
export const rawMessage = z.object({
	id: z.number(),
	thread_id: z.number(),
	role: z.string(),
	content: z.unknown(),
	author_id: z.string().nullable(),
	created_at: z.string(),
	turn_id: z.string().nullable().optional(),
});

export type RawMessage = z.infer<typeof rawMessage>;

/**
 * Suggested Action Pill schema for contextual 1-click execution chips (Story 21.11).
 */
export const suggestedActionSchema = z.object({
	id: z.string(),
	label: z.string(),
	icon: z.string().default("sparkles"),
	action_type: z.string(),
	prompt_template: z.string(),
	cost_credits: z.number().optional().nullable(),
	payload: z.record(z.string(), z.unknown()).optional().nullable(),
});

export type SuggestedAction = z.infer<typeof suggestedActionSchema>;
