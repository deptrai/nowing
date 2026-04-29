import { describe, expect, it } from "vitest";
import { applyOrchestraEvent, type OrchestraState } from "@/atoms/chat/orchestra.atom";

const EMPTY_STATE: OrchestraState = {
	sessions: new Map(),
	lastSpawnedSessionId: null,
	pendingAgentResults: new Map(),
};

const SESSION_ID = "sess-abc123";
const AGENT_1 = "agent-1";
const AGENT_2 = "agent-2";

describe("applyOrchestraEvent", () => {
	describe("orchestra-spawn", () => {
		it("creates a new session with the spawned agent queued", () => {
			const next = applyOrchestraEvent(EMPTY_STATE, {
				type: "orchestra-spawn",
				data: {
					sessionId: SESSION_ID,
					agentId: AGENT_1,
					agentName: "CoinGecko",
					agentType: "price",
				},
			});

			expect(next.lastSpawnedSessionId).toBe(SESSION_ID);
			const session = next.sessions.get(SESSION_ID)!;
			expect(session).toBeDefined();
			expect(session.outcome).toBe("running");
			const agent = session.agents.get(AGENT_1)!;
			expect(agent.status).toBe("queued");
			expect(agent.agentName).toBe("CoinGecko");
		});

		it("adds additional agents to existing session", () => {
			const afterFirst = applyOrchestraEvent(EMPTY_STATE, {
				type: "orchestra-spawn",
				data: {
					sessionId: SESSION_ID,
					agentId: AGENT_1,
					agentName: "CoinGecko",
					agentType: "price",
				},
			});
			const afterSecond = applyOrchestraEvent(afterFirst, {
				type: "orchestra-spawn",
				data: {
					sessionId: SESSION_ID,
					agentId: AGENT_2,
					agentName: "Binance",
					agentType: "exchange",
				},
			});

			const session = afterSecond.sessions.get(SESSION_ID)!;
			expect(session.agents.size).toBe(2);
			expect(session.agents.get(AGENT_2)?.agentName).toBe("Binance");
		});
	});

	describe("orchestra-update", () => {
		it("sets agent status to running", () => {
			const withSession = applyOrchestraEvent(EMPTY_STATE, {
				type: "orchestra-spawn",
				data: {
					sessionId: SESSION_ID,
					agentId: AGENT_1,
					agentName: "CoinGecko",
					agentType: "price",
				},
			});
			const updated = applyOrchestraEvent(withSession, {
				type: "orchestra-update",
				data: { sessionId: SESSION_ID, agentId: AGENT_1, status: "running" },
			});

			const agent = updated.sessions.get(SESSION_ID)!.agents.get(AGENT_1)!;
			expect(agent.status).toBe("running");
		});

		it("returns original state if session not found", () => {
			const result = applyOrchestraEvent(EMPTY_STATE, {
				type: "orchestra-update",
				data: { sessionId: "nonexistent", agentId: AGENT_1, status: "running" },
			});
			expect(result).toBe(EMPTY_STATE);
		});
	});

	describe("orchestra-done", () => {
		it("marks agent done and increments successCount", () => {
			let state = applyOrchestraEvent(EMPTY_STATE, {
				type: "orchestra-spawn",
				data: {
					sessionId: SESSION_ID,
					agentId: AGENT_1,
					agentName: "CoinGecko",
					agentType: "price",
				},
			});
			state = applyOrchestraEvent(state, {
				type: "orchestra-done",
				data: { sessionId: SESSION_ID, agentId: AGENT_1, citationIds: ["cit-1", "cit-2"] },
			});

			const agent = state.sessions.get(SESSION_ID)!.agents.get(AGENT_1)!;
			expect(agent.status).toBe("done");
			expect(agent.citationIds).toEqual(["cit-1", "cit-2"]);
			expect(state.sessions.get(SESSION_ID)!.successCount).toBe(1);
		});
	});

	describe("orchestra-fail", () => {
		it("marks agent failed with reason and increments failedCount", () => {
			let state = applyOrchestraEvent(EMPTY_STATE, {
				type: "orchestra-spawn",
				data: {
					sessionId: SESSION_ID,
					agentId: AGENT_1,
					agentName: "CoinGecko",
					agentType: "price",
				},
			});
			state = applyOrchestraEvent(state, {
				type: "orchestra-fail",
				data: {
					sessionId: SESSION_ID,
					agentId: AGENT_1,
					errorCode: "rate_limit",
					errorMessage: "Too many requests",
				},
			});

			const agent = state.sessions.get(SESSION_ID)!.agents.get(AGENT_1)!;
			expect(agent.status).toBe("failed");
			expect(agent.failReason).toBe("rate_limit");
			expect(agent.failMessage).toBe("Too many requests");
			expect(state.sessions.get(SESSION_ID)!.failedCount).toBe(1);
		});
	});

	describe("orchestra-cancel", () => {
		it("marks agent cancelled with cancelled_by_user reason", () => {
			let state = applyOrchestraEvent(EMPTY_STATE, {
				type: "orchestra-spawn",
				data: {
					sessionId: SESSION_ID,
					agentId: AGENT_1,
					agentName: "CoinGecko",
					agentType: "price",
				},
			});
			state = applyOrchestraEvent(state, {
				type: "orchestra-cancel",
				data: { sessionId: SESSION_ID, agentId: AGENT_1 },
			});

			const agent = state.sessions.get(SESSION_ID)!.agents.get(AGENT_1)!;
			expect(agent.status).toBe("cancelled");
			expect(agent.failReason).toBe("cancelled_by_user");
		});
	});

	describe("orchestra-complete", () => {
		it("sets outcome to success when all agents done", () => {
			let state = applyOrchestraEvent(EMPTY_STATE, {
				type: "orchestra-spawn",
				data: {
					sessionId: SESSION_ID,
					agentId: AGENT_1,
					agentName: "CoinGecko",
					agentType: "price",
				},
			});
			state = applyOrchestraEvent(state, {
				type: "orchestra-done",
				data: { sessionId: SESSION_ID, agentId: AGENT_1 },
			});
			state = applyOrchestraEvent(state, {
				type: "orchestra-complete",
				data: { sessionId: SESSION_ID, agentIds: [AGENT_1], citationCount: 3 },
			});

			const session = state.sessions.get(SESSION_ID)!;
			expect(session.outcome).toBe("success");
			expect(session.completedAt).not.toBeNull();
			expect(session.totalMs).not.toBeNull();
			expect(session.p95Bucket).toBeDefined();
		});

		it("sets outcome to partial when some agents failed", () => {
			let state = applyOrchestraEvent(EMPTY_STATE, {
				type: "orchestra-spawn",
				data: { sessionId: SESSION_ID, agentId: AGENT_1, agentName: "A1", agentType: "t" },
			});
			state = applyOrchestraEvent(state, {
				type: "orchestra-spawn",
				data: { sessionId: SESSION_ID, agentId: AGENT_2, agentName: "A2", agentType: "t" },
			});
			state = applyOrchestraEvent(state, {
				type: "orchestra-done",
				data: { sessionId: SESSION_ID, agentId: AGENT_1 },
			});
			state = applyOrchestraEvent(state, {
				type: "orchestra-fail",
				data: {
					sessionId: SESSION_ID,
					agentId: AGENT_2,
					errorCode: "timeout",
					errorMessage: "Timed out",
				},
			});
			state = applyOrchestraEvent(state, {
				type: "orchestra-complete",
				data: { sessionId: SESSION_ID, agentIds: [AGENT_1, AGENT_2], citationCount: 1 },
			});

			expect(state.sessions.get(SESSION_ID)!.outcome).toBe("partial");
		});

		it("sets outcome to failed when all agents failed", () => {
			let state = applyOrchestraEvent(EMPTY_STATE, {
				type: "orchestra-spawn",
				data: { sessionId: SESSION_ID, agentId: AGENT_1, agentName: "A1", agentType: "t" },
			});
			state = applyOrchestraEvent(state, {
				type: "orchestra-fail",
				data: {
					sessionId: SESSION_ID,
					agentId: AGENT_1,
					errorCode: "unavailable",
					errorMessage: "Down",
				},
			});
			state = applyOrchestraEvent(state, {
				type: "orchestra-complete",
				data: { sessionId: SESSION_ID, agentIds: [AGENT_1], citationCount: 0 },
			});

			expect(state.sessions.get(SESSION_ID)!.outcome).toBe("failed");
		});
	});

	describe("happy-path: 4 agents full lifecycle", () => {
		it("tracks all state transitions correctly", () => {
			const agents = ["a1", "a2", "a3", "a4"];
			let state = EMPTY_STATE;

			// Spawn all 4
			for (const id of agents) {
				state = applyOrchestraEvent(state, {
					type: "orchestra-spawn",
					data: {
						sessionId: SESSION_ID,
						agentId: id,
						agentName: id.toUpperCase(),
						agentType: "crypto",
					},
				});
			}
			expect(state.sessions.get(SESSION_ID)!.agents.size).toBe(4);

			// Update all to running
			for (const id of agents) {
				state = applyOrchestraEvent(state, {
					type: "orchestra-update",
					data: { sessionId: SESSION_ID, agentId: id, status: "running" },
				});
			}

			// 3 done, 1 failed
			for (const id of agents.slice(0, 3)) {
				state = applyOrchestraEvent(state, {
					type: "orchestra-done",
					data: { sessionId: SESSION_ID, agentId: id, citationIds: [`cit-${id}`] },
				});
			}
			state = applyOrchestraEvent(state, {
				type: "orchestra-fail",
				data: {
					sessionId: SESSION_ID,
					agentId: "a4",
					errorCode: "timeout",
					errorMessage: "Timed out",
				},
			});

			// Complete
			state = applyOrchestraEvent(state, {
				type: "orchestra-complete",
				data: { sessionId: SESSION_ID, agentIds: agents, citationCount: 3 },
			});

			const session = state.sessions.get(SESSION_ID)!;
			expect(session.successCount).toBe(3);
			expect(session.failedCount).toBe(1);
			expect(session.outcome).toBe("partial");
			expect(session.p95Bucket).toBeDefined();
		});
	});
});
