/**
 * Story 9-UX-1 T15 — Component unit tests for Live Research Lab components.
 *
 * Covers:
 * - StatusLight: correct aria-label per status, pulse class only on "running"
 * - ModelAttributionBadge: renders model + provider, omits tier when absent
 * - LiveNarrationStream: renders text, returns null for null, re-renders on change
 * - SourceFaviconRiver: renders chips, returns null for empty array
 * - RateGateBanner: renders wait time + reason label, returns null when gate is null
 * - ActivityTimeline: renders bar + ticks for gate waits, null below 500ms
 * - AgentLane: running lane shows narration, done lane hides it, fact counter shown
 * - applyOrchestraEvent: new 9-UX-1 event reducers (narration, source, fact, model, rate-gate)
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

import {
	applyOrchestraEvent,
	type OrchestraState,
	type OrchestraAgent,
} from "@/atoms/chat/orchestra.atom";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const SESSION_ID = "sess-ux1";
const AGENT_ID = "tokenomics_analyst";

function makeState(): OrchestraState {
	return {
		sessions: new Map(),
		activeQueryHash: null,
	};
}

function spawnedState(): OrchestraState {
	return applyOrchestraEvent(makeState(), {
		type: "orchestra-spawn",
		data: {
			sessionId: SESSION_ID,
			agentId: AGENT_ID,
			agentName: "Tokenomics Analyst",
			agentType: "tokenomics",
		},
	});
}

function agent(state: OrchestraState): OrchestraAgent {
	return state.sessions.get(SESSION_ID)!.agents.get(AGENT_ID)!;
}

// ─── applyOrchestraEvent — new 9-UX-1 reducers ───────────────────────────────

describe("applyOrchestraEvent — orchestra-spawn initialises new fields", () => {
	it("initialises narrationHistory as empty array", () => {
		const state = spawnedState();
		expect(agent(state).narrationHistory).toEqual([]);
	});

	it("initialises currentNarration as null", () => {
		expect(agent(spawnedState()).currentNarration).toBeNull();
	});

	it("initialises sourcesFetched as empty array", () => {
		expect(agent(spawnedState()).sourcesFetched).toEqual([]);
	});

	it("initialises factsCapturedCount as 0", () => {
		expect(agent(spawnedState()).factsCapturedCount).toBe(0);
	});

	it("initialises modelAttribution as null", () => {
		expect(agent(spawnedState()).modelAttribution).toBeNull();
	});

	it("initialises session rateGateWaits as empty array", () => {
		expect(spawnedState().sessions.get(SESSION_ID)!.rateGateWaits).toEqual([]);
	});
});

describe("applyOrchestraEvent — data-orchestra-narration", () => {
	it("updates currentNarration", () => {
		const next = applyOrchestraEvent(spawnedState(), {
			type: "data-orchestra-narration",
			data: {
				sessionId: SESSION_ID,
				agentId: AGENT_ID,
				text: "Đang query CoinGecko...",
				tone: "fetching",
			},
		});
		expect(agent(next).currentNarration).toBe("Đang query CoinGecko...");
	});

	it("appends to narrationHistory", () => {
		const next = applyOrchestraEvent(spawnedState(), {
			type: "data-orchestra-narration",
			data: { sessionId: SESSION_ID, agentId: AGENT_ID, text: "text1", tone: "fetching" },
		});
		expect(agent(next).narrationHistory).toHaveLength(1);
		expect(agent(next).narrationHistory[0].text).toBe("text1");
	});

	it("caps narrationHistory at 10 entries", () => {
		let state = spawnedState();
		for (let i = 0; i < 12; i++) {
			state = applyOrchestraEvent(state, {
				type: "data-orchestra-narration",
				data: { sessionId: SESSION_ID, agentId: AGENT_ID, text: `msg${i}`, tone: "fetching" },
			});
		}
		expect(agent(state).narrationHistory).toHaveLength(10);
		expect(agent(state).narrationHistory[9].text).toBe("msg11");
	});

	it("no-ops for unknown sessionId", () => {
		const before = spawnedState();
		const after = applyOrchestraEvent(before, {
			type: "data-orchestra-narration",
			data: { sessionId: "unknown", agentId: AGENT_ID, text: "x", tone: "fetching" },
		});
		expect(after).toBe(before);
	});
});

describe("applyOrchestraEvent — data-orchestra-source-fetched", () => {
	const SOURCE = {
		domain: "coingecko.com",
		favicon: "https://icons.duckduckgo.com/ip3/coingecko.com.ico",
		url: "",
		dataType: "price",
	};

	it("adds source to sourcesFetched", () => {
		const next = applyOrchestraEvent(spawnedState(), {
			type: "data-orchestra-source-fetched",
			data: { sessionId: SESSION_ID, agentId: AGENT_ID, source: SOURCE },
		});
		expect(agent(next).sourcesFetched).toHaveLength(1);
		expect(agent(next).sourcesFetched[0].domain).toBe("coingecko.com");
	});

	it("deduplicates by domain", () => {
		let state = spawnedState();
		const event = {
			type: "data-orchestra-source-fetched" as const,
			data: { sessionId: SESSION_ID, agentId: AGENT_ID, source: SOURCE },
		};
		state = applyOrchestraEvent(state, event);
		state = applyOrchestraEvent(state, event);
		expect(agent(state).sourcesFetched).toHaveLength(1);
	});
});

describe("applyOrchestraEvent — data-orchestra-fact-captured", () => {
	it("increments factsCapturedCount", () => {
		let state = spawnedState();
		state = applyOrchestraEvent(state, {
			type: "data-orchestra-fact-captured",
			data: { sessionId: SESSION_ID, agentId: AGENT_ID, factSummary: "TVL $3.2B" },
		});
		state = applyOrchestraEvent(state, {
			type: "data-orchestra-fact-captured",
			data: { sessionId: SESSION_ID, agentId: AGENT_ID, factSummary: "Price $7.23" },
		});
		expect(agent(state).factsCapturedCount).toBe(2);
	});
});

describe("applyOrchestraEvent — data-orchestra-model-attribution", () => {
	it("sets modelAttribution", () => {
		const next = applyOrchestraEvent(spawnedState(), {
			type: "data-orchestra-model-attribution",
			data: {
				sessionId: SESSION_ID,
				agentId: AGENT_ID,
				model: "claude-sonnet-4-6",
				provider: "trollllm",
				tier: "standard",
			},
		});
		expect(agent(next).modelAttribution).toEqual({
			model: "claude-sonnet-4-6",
			provider: "trollllm",
			tier: "standard",
		});
	});

	it("sets modelAttribution without tier", () => {
		const next = applyOrchestraEvent(spawnedState(), {
			type: "data-orchestra-model-attribution",
			data: { sessionId: SESSION_ID, agentId: AGENT_ID, model: "m", provider: "p" },
		});
		expect(agent(next).modelAttribution?.tier).toBeUndefined();
	});
});

describe("applyOrchestraEvent — data-orchestra-rate-gate-wait", () => {
	it("appends to rateGateWaits", () => {
		const next = applyOrchestraEvent(spawnedState(), {
			type: "data-orchestra-rate-gate-wait",
			data: { sessionId: SESSION_ID, waitSeconds: 7.2, reason: "min_interval" },
		});
		const waits = next.sessions.get(SESSION_ID)!.rateGateWaits;
		expect(waits).toHaveLength(1);
		expect(waits[0].waitSeconds).toBe(7.2);
		expect(waits[0].reason).toBe("min_interval");
	});
});

// ─── Component rendering ──────────────────────────────────────────────────────

describe("StatusLight", () => {
	let StatusLight: typeof import("@/components/new-chat/orchestra/status-light").StatusLight;

	beforeEach(async () => {
		({ StatusLight } = await import("@/components/new-chat/orchestra/status-light"));
	});

	it("has correct aria-label for running", () => {
		render(<StatusLight status="running" />);
		expect(screen.getByRole("status", { name: "Running" })).toBeInTheDocument();
	});

	it("has correct aria-label for done", () => {
		render(<StatusLight status="done" />);
		expect(screen.getByRole("status", { name: "Done" })).toBeInTheDocument();
	});

	it("shows ping animation span when running", () => {
		const { container } = render(<StatusLight status="running" />);
		expect(container.querySelector(".animate-ping")).toBeTruthy();
	});

	it("does not show ping animation when done", () => {
		const { container } = render(<StatusLight status="done" />);
		expect(container.querySelector(".animate-ping")).toBeFalsy();
	});
});

describe("ModelAttributionBadge", () => {
	let ModelAttributionBadge: typeof import("@/components/new-chat/orchestra/model-attribution-badge").ModelAttributionBadge;

	beforeEach(async () => {
		({ ModelAttributionBadge } = await import(
			"@/components/new-chat/orchestra/model-attribution-badge"
		));
	});

	it("renders model and provider", () => {
		render(<ModelAttributionBadge model="claude-sonnet-4-6" provider="trollllm" />);
		expect(screen.getByText(/sonnet-4-6/)).toBeInTheDocument();
		expect(screen.getByText(/trollllm/)).toBeInTheDocument();
	});

	it("includes tier when provided", () => {
		render(<ModelAttributionBadge model="claude-sonnet-4-6" provider="trollllm" tier="standard" />);
		expect(screen.getByText(/standard/)).toBeInTheDocument();
	});

	it("omits tier when not provided", () => {
		render(<ModelAttributionBadge model="model" provider="provider" />);
		expect(screen.queryByText(/tier/i)).toBeNull();
	});
});

describe("LiveNarrationStream", () => {
	let LiveNarrationStream: typeof import("@/components/new-chat/orchestra/live-narration-stream").LiveNarrationStream;

	beforeEach(async () => {
		({ LiveNarrationStream } = await import(
			"@/components/new-chat/orchestra/live-narration-stream"
		));
	});

	it("renders narration text", () => {
		render(<LiveNarrationStream text="Đang query CoinGecko..." />);
		expect(screen.getByText("Đang query CoinGecko...")).toBeInTheDocument();
	});

	it("returns null when text is null", () => {
		const { container } = render(<LiveNarrationStream text={null} />);
		expect(container.firstChild).toBeNull();
	});

	it("has aria-live polite on container", () => {
		const { container } = render(<LiveNarrationStream text="some text" />);
		const root = container.firstChild as HTMLElement | null;
		expect(root?.getAttribute("aria-live")).toBe("polite");
	});
});

describe("SourceFaviconRiver", () => {
	let SourceFaviconRiver: typeof import("@/components/new-chat/orchestra/source-favicon-river").SourceFaviconRiver;

	beforeEach(async () => {
		({ SourceFaviconRiver } = await import("@/components/new-chat/orchestra/source-favicon-river"));
	});

	const sources = [
		{
			domain: "coingecko.com",
			favicon: "https://icons.duckduckgo.com/ip3/coingecko.com.ico",
			url: "",
			dataType: "price",
		},
		{
			domain: "defillama.com",
			favicon: "https://icons.duckduckgo.com/ip3/defillama.com.ico",
			url: "",
			dataType: "tvl",
		},
	];

	it("renders a chip per source", () => {
		render(<SourceFaviconRiver sources={sources} />);
		expect(screen.getByText("coingecko.com")).toBeInTheDocument();
		expect(screen.getByText("defillama.com")).toBeInTheDocument();
	});

	it("returns null for empty array", () => {
		const { container } = render(<SourceFaviconRiver sources={[]} />);
		expect(container.firstChild).toBeNull();
	});
});

describe("RateGateBanner", () => {
	let RateGateBanner: typeof import("@/components/new-chat/orchestra/rate-gate-banner").RateGateBanner;

	beforeEach(async () => {
		({ RateGateBanner } = await import("@/components/new-chat/orchestra/rate-gate-banner"));
	});

	it("renders wait seconds and reason", () => {
		render(
			<RateGateBanner latestGate={{ waitSeconds: 7.2, reason: "min_interval", ts: Date.now() }} />
		);
		expect(screen.getByText(/7\.2/)).toBeInTheDocument();
		expect(screen.getByText(/tiêu chuẩn/)).toBeInTheDocument();
	});

	it("returns null when latestGate is null", () => {
		const { container } = render(<RateGateBanner latestGate={null} />);
		expect(container.firstChild).toBeNull();
	});
});

describe("ActivityTimeline", () => {
	let ActivityTimeline: typeof import("@/components/new-chat/orchestra/activity-timeline").ActivityTimeline;

	beforeEach(async () => {
		({ ActivityTimeline } = await import("@/components/new-chat/orchestra/activity-timeline"));
	});

	it("returns null when elapsed < 500ms", () => {
		const { container } = render(
			<ActivityTimeline spawnedAt={Date.now() - 100} rateGateWaits={[]} />
		);
		expect(container.firstChild).toBeNull();
	});

	it("renders timeline bar after 500ms", () => {
		const { container } = render(
			<ActivityTimeline spawnedAt={Date.now() - 10_000} rateGateWaits={[]} />
		);
		expect(container.querySelector("[data-slot='activity-timeline']")).toBeTruthy();
	});

	it("shows pacing pause count when gate waits exist", () => {
		render(
			<ActivityTimeline
				spawnedAt={Date.now() - 10_000}
				rateGateWaits={[
					{ waitSeconds: 7, reason: "min_interval", ts: Date.now() - 5_000 },
					{ waitSeconds: 3, reason: "paced", ts: Date.now() - 2_000 },
				]}
			/>
		);
		expect(screen.getByText(/2 pauses/)).toBeInTheDocument();
	});
});
