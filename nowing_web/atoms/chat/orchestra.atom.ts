"use client";

import { atom } from "jotai";

// ─── Shared types ─────────────────────────────────────────────────────────────

export type AgentStatus = "idle" | "queued" | "running" | "done" | "failed" | "cancelled";

export interface NarrationEvent {
	text: string;
	tone: "fetching" | "analyzing" | "synthesizing";
	ts: number;
}

export interface Source {
	domain: string;
	favicon: string;
	url: string;
	dataType: string;
}

export interface RateGateEvent {
	waitSeconds: number;
	reason: string;
	ts: number;
}

/**
 * AC11: derive degradation level from observed rate-gate activity.
 * - 0: nominal (no gates / 1 short gate)
 * - 1: paced (≥2 gate waits OR cumulative ≥10s in last 30s window)
 * - 2: heavily degraded (≥4 waits OR cumulative ≥30s in last 30s)
 */
export function deriveEscalationLevel(waits: RateGateEvent[]): 0 | 1 | 2 {
	if (waits.length === 0) return 0;
	const now = Date.now();
	const recent = waits.filter((w) => now - w.ts <= 30_000);
	const cumulative = recent.reduce((a, w) => a + w.waitSeconds, 0);
	if (recent.length >= 4 || cumulative >= 30) return 2;
	if (recent.length >= 2 || cumulative >= 10) return 1;
	return 0;
}

export type FailReason =
	| "rate_limit"
	| "rate_limit_exhausted"
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
	// 9-UX-1: live research lab fields
	narrationHistory: NarrationEvent[];
	currentNarration: string | null;
	sourcesFetched: Source[];
	factsCapturedCount: number;
	modelAttribution: { model: string; provider: string; tier?: string } | null;
	// Agent result text (streamed after orchestra-done)
	resultText?: string;
	resultLength?: number;
	resultTruncated?: boolean;
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
	// 9-UX-1: session-level rate gate history
	rateGateWaits: RateGateEvent[];
	// 9-UX-1 AC10: per-LLM-call timestamps for ActivityTimeline ticks.
	// Each entry: { ts: Date.now(), agentId: <string> }. Capped at 200.
	llmCallEvents: Array<{ ts: number; agentId: string }>;
	// ETA fix: actual wall-clock ms each completed agent took (from spawnedAt to done).
	// Used instead of total-elapsed/doneCount which is inflated by shared rate-gate waits.
	completedAgentMs: number[];
}

export interface OrchestraState {
	// NOTE: Map key is `sessionId` === `langgraph_thread_id` === `"run-{uuid}"` (unique per run).
	// This is NOT the integer chat thread_id. The BE stamps sessionId server-side in
	// stream_new_chat.py from configurable.thread_id which is set to langgraph_thread_id_override
	// ("run-{uuid}") for detached runs. Each session object also carries `queryHash` for
	// hashing/persistence, but lookups happen by sessionId.
	sessions: Map<string /* sessionId = "run-{uuid}" */, OrchestraSession>;
	/** sessionId of the most recently spawned session (T19). */
	lastSpawnedSessionId: string | null;
	/** Pending data-agent-result events keyed by `${sessionId}:${agentId}` —
	 *  buffered when arriving before orchestra-spawn or after orchestra-complete.
	 *  Drained on matching orchestra-spawn. */
	pendingAgentResults: Map<
		string,
		{ resultText: string; resultLength: number; truncated: boolean }
	>;
}

// ─── Atoms ────────────────────────────────────────────────────────────────────

export const orchestraStateAtom = atom<OrchestraState>({
	sessions: new Map(),
	lastSpawnedSessionId: null,
	pendingAgentResults: new Map(),
});

// ─── Derived atoms ────────────────────────────────────────────────────────────

/** Most recently spawned session (latest run). */
export const activeOrchestraSessionAtom = atom<OrchestraSession | null>((get) => {
	const state = get(orchestraStateAtom);
	if (!state.lastSpawnedSessionId) return null;
	return state.sessions.get(state.lastSpawnedSessionId) ?? null;
});

/** All sessions currently in "running" outcome — for multi-strip rendering (T20). */
export const activeRunSessionsAtom = atom<OrchestraSession[]>((get) => {
	const state = get(orchestraStateAtom);
	return Array.from(state.sessions.values()).filter((s) => s.outcome === "running");
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
	  }
	// 9-UX-1: Phase 2 UX events
	| {
			type: "data-orchestra-narration";
			data: {
				sessionId: string;
				agentId: string;
				text: string;
				tone: "fetching" | "analyzing" | "synthesizing";
			};
	  }
	| {
			type: "data-orchestra-source-fetched";
			data: { sessionId: string; agentId: string; source: Source };
	  }
	| {
			type: "data-orchestra-fact-captured";
			data: {
				sessionId: string;
				agentId: string;
				factSummary: string;
				value?: number;
				unit?: string;
			};
	  }
	| {
			type: "data-orchestra-model-attribution";
			data: { sessionId: string; agentId: string; model: string; provider: string; tier?: string };
	  }
	| {
			type: "data-orchestra-rate-gate-wait";
			data: { sessionId: string; waitSeconds: number; reason: string };
	  }
	| {
			type: "data-orchestra-llm-call";
			data: { sessionId: string; agentId: string };
	  }
	| {
			type: "data-agent-result";
			data: {
				sessionId?: string;
				agentId: string;
				resultText: string;
				resultLength: number;
				truncated: boolean;
			};
	  };

function p95Bucket(ms: number): "fast" | "normal" | "slow" {
	if (ms < 10_000) return "fast";
	if (ms < 30_000) return "normal";
	return "slow";
}

/**
 * Override `spawnedAt` for a session using the server-side run start time.
 * Call this before replaying DB events so per-agent elapsedMs is accurate.
 */
export function setSessionSpawnedAt(
	state: OrchestraState,
	sessionId: string,
	spawnedAt: number
): OrchestraState {
	const session = state.sessions.get(sessionId);
	if (!session) return state;
	const sessions = new Map(state.sessions);
	sessions.set(sessionId, { ...session, spawnedAt });
	return { ...state, sessions };
}

export function applyOrchestraEvent(
	state: OrchestraState,
	event: OrchestraSSEEvent & { _ts?: number }
): OrchestraState {
	const sessions = new Map(state.sessions);
	// Use server-side event timestamp when available (replay from DB) for accurate elapsed calc.
	const eventTs = typeof event._ts === "number" ? event._ts : Date.now();

	if (event.type === "orchestra-spawn") {
		const { sessionId, agentId, agentName, agentType } = event.data;
		const existing = sessions.get(sessionId);
		const agents: Map<string, OrchestraAgent> = existing ? new Map(existing.agents) : new Map();
		// Drain any pending agent-result that arrived before this spawn.
		const pendingKey = `${sessionId}:${agentId}`;
		const pending = state.pendingAgentResults.get(pendingKey);
		const pendingAgentResults = pending
			? new Map(state.pendingAgentResults)
			: state.pendingAgentResults;
		if (pending) pendingAgentResults.delete(pendingKey);
		agents.set(agentId, {
			agentId,
			agentName,
			agentType,
			status: "queued",
			elapsedMs: 0,
			narrationHistory: [],
			currentNarration: null,
			sourcesFetched: [],
			factsCapturedCount: 0,
			modelAttribution: null,
			...(pending
				? {
						resultText: pending.resultText,
						resultLength: pending.resultLength,
						resultTruncated: pending.truncated,
					}
				: {}),
		});
		const session: OrchestraSession = existing
			? { ...existing, agents }
			: {
					queryHash: sessionId,
					sessionId,
					agents,
					spawnedAt: eventTs,
					completedAt: null,
					outcome: "running",
					totalMs: null,
					successCount: 0,
					failedCount: 0,
					p95Bucket: null,
					milestone30sFired: false,
					milestone: null,
					rateGateWaits: [],
					llmCallEvents: [],
					completedAgentMs: [],
				};
		sessions.set(sessionId, session);
		return { ...state, sessions, lastSpawnedSessionId: sessionId, pendingAgentResults };
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
				elapsedMs: eventTs - session.spawnedAt,
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
		const agentElapsedMs = eventTs - session.spawnedAt;
		if (agent) {
			agents.set(agentId, {
				...agent,
				status: "done",
				citationIds,
				elapsedMs: agentElapsedMs,
			});
		}
		const successCount = Array.from(agents.values()).filter((a) => a.status === "done").length;
		const completedAgentMs = [...session.completedAgentMs, agentElapsedMs];
		sessions.set(sessionId, { ...session, agents, successCount, completedAgentMs });
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
				elapsedMs: eventTs - session.spawnedAt,
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
				elapsedMs: eventTs - session.spawnedAt,
			});
		}
		sessions.set(sessionId, { ...session, agents });
		return { ...state, sessions };
	}

	if (event.type === "orchestra-complete") {
		const { sessionId } = event.data;
		const session = sessions.get(sessionId);
		if (!session) return state;
		const completedAt = eventTs;
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
					elapsedMs: eventTs - session.spawnedAt,
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

		// P13: cap retained completed sessions at MAX_RETAINED to bound memory.
		// Evict the oldest completed sessions while keeping any still-running ones
		// and the just-completed one. Also evict their pending agent-result entries
		// (otherwise pendingAgentResults grows unbounded across long sessions).
		const MAX_RETAINED = 5;
		const completedEntries = Array.from(sessions.entries())
			.filter(([, s]) => s.completedAt !== null)
			.sort(([, a], [, b]) => (a.completedAt ?? 0) - (b.completedAt ?? 0));
		const evictedSessionIds: string[] = [];
		while (completedEntries.length > MAX_RETAINED) {
			const [staleId] = completedEntries.shift()!;
			sessions.delete(staleId);
			evictedSessionIds.push(staleId);
		}
		// Drop pending entries for evicted sessions.
		let pendingAgentResults = state.pendingAgentResults;
		if (evictedSessionIds.length > 0) {
			pendingAgentResults = new Map(state.pendingAgentResults);
			for (const sid of evictedSessionIds) {
				for (const key of pendingAgentResults.keys()) {
					if (key.startsWith(`${sid}:`)) pendingAgentResults.delete(key);
				}
			}
		}
		// Hard cap: never let pendingAgentResults exceed MAX_PENDING.
		const MAX_PENDING = 50;
		if (pendingAgentResults.size > MAX_PENDING) {
			pendingAgentResults =
				pendingAgentResults === state.pendingAgentResults
					? new Map(state.pendingAgentResults)
					: pendingAgentResults;
			const overflow = pendingAgentResults.size - MAX_PENDING;
			const iter = pendingAgentResults.keys();
			for (let i = 0; i < overflow; i++) {
				const k = iter.next().value;
				if (k) pendingAgentResults.delete(k);
			}
		}

		return { ...state, sessions, pendingAgentResults };
	}

	if (event.type === "data-orchestra-narration") {
		const { sessionId, agentId, text, tone } = event.data;
		const session = sessions.get(sessionId);
		if (!session) return state;
		const agents = new Map(session.agents);
		const agent = agents.get(agentId);
		if (agent) {
			const narrationEvent: NarrationEvent = { text, tone, ts: Date.now() };
			const history = [...agent.narrationHistory, narrationEvent].slice(-10);
			agents.set(agentId, { ...agent, narrationHistory: history, currentNarration: text });
		}
		sessions.set(sessionId, { ...session, agents });
		return { ...state, sessions };
	}

	if (event.type === "data-orchestra-source-fetched") {
		const { sessionId, agentId, source } = event.data;
		const session = sessions.get(sessionId);
		if (!session) return state;
		const agents = new Map(session.agents);
		const agent = agents.get(agentId);
		if (agent) {
			const already = agent.sourcesFetched.some((s) => s.domain === source.domain);
			if (!already) {
				agents.set(agentId, { ...agent, sourcesFetched: [...agent.sourcesFetched, source] });
			}
		}
		sessions.set(sessionId, { ...session, agents });
		return { ...state, sessions };
	}

	if (event.type === "data-orchestra-fact-captured") {
		const { sessionId, agentId } = event.data;
		const session = sessions.get(sessionId);
		if (!session) return state;
		const agents = new Map(session.agents);
		const agent = agents.get(agentId);
		if (agent) {
			agents.set(agentId, { ...agent, factsCapturedCount: agent.factsCapturedCount + 1 });
		}
		sessions.set(sessionId, { ...session, agents });
		return { ...state, sessions };
	}

	if (event.type === "data-orchestra-model-attribution") {
		const { sessionId, agentId, model, provider, tier } = event.data;
		const session = sessions.get(sessionId);
		if (!session) return state;
		const agents = new Map(session.agents);
		const agent = agents.get(agentId);
		if (agent) {
			agents.set(agentId, { ...agent, modelAttribution: { model, provider, tier } });
		}
		sessions.set(sessionId, { ...session, agents });
		return { ...state, sessions };
	}

	if (event.type === "data-orchestra-rate-gate-wait") {
		const { sessionId, waitSeconds, reason } = event.data;
		const session = sessions.get(sessionId);
		if (!session) return state;
		const rateGateWaits = [...session.rateGateWaits, { waitSeconds, reason, ts: Date.now() }];
		sessions.set(sessionId, { ...session, rateGateWaits });
		return { ...state, sessions };
	}

	if (event.type === "data-orchestra-llm-call") {
		const { sessionId, agentId } = event.data;
		const session = sessions.get(sessionId);
		if (!session) return state;
		// AC10: cap at 200 entries to bound memory in long sessions.
		const llmCallEvents = [...session.llmCallEvents, { ts: Date.now(), agentId }].slice(-200);
		sessions.set(sessionId, { ...session, llmCallEvents });
		return { ...state, sessions };
	}

	if (event.type === "data-agent-result") {
		const { sessionId, agentId, resultText, resultLength, truncated } = event.data;
		// Resolve session: prefer explicit sessionId (BE _orchestra_writer stamps it);
		// fall back to lastSpawnedSessionId for safety.
		const resolvedSessionId = sessionId ?? state.lastSpawnedSessionId ?? null;
		const session = resolvedSessionId ? sessions.get(resolvedSessionId) : undefined;
		const agent = session?.agents.get(agentId);

		if (session && agent) {
			// Happy path: session and agent slot both exist → patch.
			const agents = new Map(session.agents);
			agents.set(agentId, {
				...agent,
				resultText,
				resultLength,
				resultTruncated: truncated,
			});
			sessions.set(session.sessionId, { ...session, agents });
			return { ...state, sessions };
		}

		// Buffer when session/agent slot doesn't exist yet (event arrived before
		// orchestra-spawn) or session is already complete (event arrived after
		// orchestra-complete). Drained on next matching orchestra-spawn or evicted
		// when its session is evicted from the sessions Map (orchestra-complete).
		if (resolvedSessionId) {
			const pendingAgentResults = new Map(state.pendingAgentResults);
			pendingAgentResults.set(`${resolvedSessionId}:${agentId}`, {
				resultText,
				resultLength,
				truncated,
			});
			// Hard cap: prevent unbounded growth (FIFO eviction of oldest entries).
			const MAX_PENDING = 50;
			while (pendingAgentResults.size > MAX_PENDING) {
				const oldest = pendingAgentResults.keys().next().value;
				if (oldest) pendingAgentResults.delete(oldest);
				else break;
			}
			return { ...state, pendingAgentResults };
		}
		return state;
	}

	return state;
}
