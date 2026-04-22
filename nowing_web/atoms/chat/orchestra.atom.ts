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
	sessions: Map<string /* queryHash */, OrchestraSession>;
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
		const { sessionId, agentId, milestone } = event.data;
		const session = sessions.get(sessionId);
		if (!session) return state;
		const agents = new Map(session.agents);
		const agent = agents.get(agentId);
		if (agent) {
			agents.set(agentId, {
				...agent,
				status: "running",
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
		const successCount = Array.from(session.agents.values()).filter(
			(a) => a.status === "done"
		).length;
		const failedCount = Array.from(session.agents.values()).filter(
			(a) => a.status === "failed" || a.status === "cancelled"
		).length;
		const outcome: OrchestraOutcome =
			failedCount === 0 ? "success" : successCount === 0 ? "failed" : "partial";
		sessions.set(sessionId, {
			...session,
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
