import { json, string, table } from "@rocicorp/zero";

/**
 * Persists orchestra session state across page refreshes via Rocicorp Zero.
 * PK: query_hash = sha256(query + user_id)[:16] — computed FE-side.
 * Rows are user-scoped (RLS: user_id enforced at Zero permissions layer).
 */
export const orchestraSessionsTable = table("orchestra_sessions")
	.columns({
		queryHash: string().from("query_hash"),
		sessionId: string().from("session_id"),
		agents: json().from("agents"), // serialized AgentSummarySnapshot[]
		spawnedAt: string().from("spawned_at"), // ISO timestamp
		completedAt: string().optional().from("completed_at"),
		outcome: string().from("outcome"), // OrchestraOutcome
		totalMs: string().optional().from("total_ms"), // stored as string for nullable compat
	})
	.primaryKey("queryHash");
