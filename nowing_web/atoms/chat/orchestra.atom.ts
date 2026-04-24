"use client";

import { atom } from "jotai";

// ─── Shared types ─────────────────────────────────────────────────────────────

export type AgentStatus = "idle" | "queued" | "running" | "done" | "failed" | "cancelled";

export type FailReason =
	| "rate_limit"
	| "timeout"
	| "unavailable"
	| "circuit_open"
	| "cancelled_by_user";

export type OrchestraOutcome = "running" | "success" | "partial" | "failed" | "cancelled";

export interface AgentSummary {
	factCount: number;
	sources: string[];
}

export interface OrchestraAgent {
	agentId: string;
	agentName: string;
	agentType: string;
	displayName?: string;
	estimatedP50Ms?: number;
	toolsCount?: number;
	status: AgentStatus;
	elapsedMs: number;
	summary?: AgentSummary;
	failReason?: FailReason;
	failMessage?: string;
	citationIds?: string[];
}

export interface OrchestraSession {
	queryHash: string;
	sessionId: string;
	agents: Map<string /* agentId */, OrchestraAgent>;
	spawnedAt: number; // Date.now()
	completedAt: number | null;
	outcome: OrchestraOutcome;
	totalMs: number | null;
	successCount: number;
	failedCount: number;
	p95Bucket: "fast" | "normal" | "slow" | null;
	milestone30sFired: boolean;
	milestone: string | null;
}

export interface OrchestraState {
	// NOTE: Map key is `sessionId` (not `queryHash`). Each session object still carries
	// `queryHash` for hashing/persistence, but lookups happen by sessionId (the discriminator
	// the SSE stream uses). See reducer calls: sessions.get(event.data.sessionId).
	sessions: Map<string /* sessionId */, OrchestraSession>;
	activeQueryHash: string | null;
}

// ─── Atoms ────────────────────────────────────────────────────────────────────

export const orchestraStateAtom = atom<OrchestraState>({
	sessions: new Map(),
	activeQueryHash: null,
});

// ─── Derived atoms ────────────────────────────────────────────────────────────

/** Active session derived from orchestraStateAtom */
export const activeOrchestraSessionAtom = atom<OrchestraSession | null>((get) => {
	const state = get(orchestraStateAtom);
	if (!state.activeQueryHash) return null;
	return state.sessions.get(state.activeQueryHash) ?? null;
});

// ─── SSE event reducers ───────────────────────────────────────────────────────

type OrchestraSSEEvent =
	| {
			type: "orchestra-spawn";
			data: { sessionId: string; agentId: string; agentName: string; agentType: string };
	  }
	| {
			type: "orchestra-update";
			data: {
				sessionId: string;
				agentId: string;
				status: "running" | "waiting" | "degraded";
				progress?: number;
				milestone?: string;
			};
	  }
	| { type: "orchestra-done"; data: { sessionId: string; agentId: string; citationIds?: string[] } }
	| {
			type: "orchestra-fail";
			data: { sessionId: string; agentId: string; errorCode: string; errorMessage: string };
	  }
	| { type: "orchestra-cancel"; data: { sessionId: string; agentId: string } }
	| {
			type: "orchestra-complete";
			data: { sessionId: string; agentIds: string[]; citationCount: number };
	  };

function p95Bucket(ms: number): "fast" | "normal" | "slow" {
	if (ms < 10_000) return "fast";
	if (ms < 30_000) return "normal";
	return "slow";
}

export function applyOrchestraEvent(
	state: OrchestraState,
	event: OrchestraSSEEvent
): OrchestraState {
	const sessions = new Map(state.sessions);

	if (event.type === "orchestra-spawn") {
		const { sessionId, agentId, agentName, agentType } = event.data;
		const existing = sessions.get(sessionId);
		const agents: Map<string, OrchestraAgent> = existing ? new Map(existing.agents) : new Map();
		agents.set(agentId, {
			agentId,
			agentName,
			agentType,
			status: "queued",
			elapsedMs: 0,
		});
		const session: OrchestraSession = existing
			? { ...existing, agents }
			: {
					queryHash: sessionId,
					sessionId,
					agents,
					spawnedAt: Date.now(),
					completedAt: null,
					outcome: "running",
					totalMs: null,
					successCount: 0,
					failedCount: 0,
					p95Bucket: null,
					milestone30sFired: false,
					milestone: null,
				};
		sessions.set(sessionId, session);
		return { sessions, activeQueryHash: sessionId };
	}

	if (event.type === "orchestra-update") {
		const { sessionId, agentId, status: eventStatus, milestone } = event.data;
		const session = sessions.get(sessionId);
		if (!session) return state;
		const agents = new Map(session.agents);
		const agent = agents.get(agentId);
		if (agent) {
			// P2: propagate event.data.status ("running" | "waiting" | "degraded")
			// instead of always overwriting with "running". Map non-AgentStatus values
			// conservatively: "waiting" → "queued", "degraded" → "running" (still
			// progressing, just slower), "running" → "running".
			const mapped: AgentStatus =
				eventStatus === "waiting" ? "queued" : eventStatus === "degraded" ? "running" : "running";
			agents.set(agentId, {
				...agent,
				status: mapped,
				elapsedMs: Date.now() - session.spawnedAt,
			});
		}
		sessions.set(sessionId, { ...session, agents });
		if (milestone) {
			const updated = sessions.get(sessionId)!;
			sessions.set(sessionId, { ...updated, milestone });
		}
		return { ...state, sessions };
	}

	if (event.type === "orchestra-done") {
		const { sessionId, agentId, citationIds } = event.data;
		const session = sessions.get(sessionId);
		if (!session) return state;
		const agents = new Map(session.agents);
		const agent = agents.get(agentId);
		if (agent) {
			agents.set(agentId, {
				...agent,
				status: "done",
				citationIds,
				elapsedMs: Date.now() - session.spawnedAt,
			});
		}
		const successCount = Array.from(agents.values()).filter((a) => a.status === "done").length;
		sessions.set(sessionId, { ...session, agents, successCount });
		return { ...state, sessions };
	}

	if (event.type === "orchestra-fail") {
		const { sessionId, agentId, errorCode, errorMessage } = event.data;
		const session = sessions.get(sessionId);
		if (!session) return state;
		const agents = new Map(session.agents);
		const agent = agents.get(agentId);
		if (agent) {
			agents.set(agentId, {
				...agent,
				status: "failed",
				failReason: errorCode as FailReason,
				failMessage: errorMessage,
				elapsedMs: Date.now() - session.spawnedAt,
			});
		}
		const failedCount = Array.from(agents.values()).filter((a) => a.status === "failed").length;
		sessions.set(sessionId, { ...session, agents, failedCount });
		return { ...state, sessions };
	}

	if (event.type === "orchestra-cancel") {
		const { sessionId, agentId } = event.data;
		const session = sessions.get(sessionId);
		if (!session) return state;
		const agents = new Map(session.agents);
		const agent = agents.get(agentId);
		if (agent) {
			agents.set(agentId, {
				...agent,
				status: "cancelled",
				failReason: "cancelled_by_user",
				elapsedMs: Date.now() - session.spawnedAt,
			});
		}
		sessions.set(sessionId, { ...session, agents });
		return { ...state, sessions };
	}

	if (event.type === "orchestra-complete") {
		const { sessionId } = event.data;
		const session = sessions.get(sessionId);
		if (!session) return state;
		const completedAt = Date.now();
		const totalMs = completedAt - session.spawnedAt;
		// P5: force-transition any lingering running/queued/idle agents to "failed".
		// If the backend emits orchestra-complete without a matching done/fail for an
		// agent (out-of-order SSE or dropped event), the row would spin forever while
		// the session is marked done. Terminate them here.
		const agents = new Map(session.agents);
		for (const [id, a] of agents) {
			if (a.status === "running" || a.status === "queued" || a.status === "idle") {
				agents.set(id, {
					...a,
					status: "failed",
					failReason: "unavailable",
					failMessage: "Agent did not complete before orchestra-complete event",
					elapsedMs: Date.now() - session.spawnedAt,
				});
			}
		}
		const values = Array.from(agents.values());
		const successCount = values.filter((a) => a.status === "done").length;
		const cancelledCount = values.filter((a) => a.status === "cancelled").length;
		const trueFailedCount = values.filter((a) => a.status === "failed").length;
		const failedCount = trueFailedCount + cancelledCount;
		// P3: surface "cancelled" outcome when the user cancelled everything. Ordering:
		// all success → success; all cancelled and nothing succeeded → cancelled;
		// any real failure mixed with zero success → failed; otherwise partial.
		const outcome: OrchestraOutcome =
			failedCount === 0
				? "success"
				: successCount === 0 && trueFailedCount === 0 && cancelledCount > 0
					? "cancelled"
					: successCount === 0
						? "failed"
						: "partial";
		sessions.set(sessionId, {
			...session,
			agents,
			completedAt,
			totalMs,
			successCount,
			failedCount,
			outcome,
			p95Bucket: p95Bucket(totalMs),
		});
		return { ...state, sessions };
	}

	return state;
}
