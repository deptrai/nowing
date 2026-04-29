import type { Meta, StoryObj } from "@storybook/react";
import { ActivityTimeline } from "./activity-timeline";
import { AgentLane } from "./agent-lane";
import { LiveNarrationStream } from "./live-narration-stream";
import { ModelAttributionBadge } from "./model-attribution-badge";
import { RateGateBanner } from "./rate-gate-banner";
import { SourceFaviconRiver } from "./source-favicon-river";
import { StatusLight } from "./status-light";

// ─── StatusLight ──────────────────────────────────────────────────────────────

const statusLightMeta: Meta<typeof StatusLight> = {
	title: "crypto-orchestra/StatusLight",
	component: StatusLight,
};
export default statusLightMeta;

export const AllStatuses: StoryObj<typeof StatusLight> = {
	render: () => (
		<div className="flex items-center gap-4 p-4">
			{(["idle", "queued", "running", "done", "failed", "cancelled"] as const).map((s) => (
				<div key={s} className="flex flex-col items-center gap-1 text-xs">
					<StatusLight status={s} />
					<span>{s}</span>
				</div>
			))}
		</div>
	),
};

// ─── ModelAttributionBadge ────────────────────────────────────────────────────

export const ModelBadge: StoryObj<typeof ModelAttributionBadge> = {
	render: () => (
		<div className="flex flex-col gap-2 p-4">
			<ModelAttributionBadge model="claude-sonnet-4-6" provider="trollllm" tier="standard" />
			<ModelAttributionBadge model="claude-opus-4-7" provider="anthropic" />
		</div>
	),
};

// ─── LiveNarrationStream ──────────────────────────────────────────────────────

export const NarrationStream: StoryObj<typeof LiveNarrationStream> = {
	render: () => (
		<div className="max-w-sm p-4">
			<LiveNarrationStream text="Đang query CoinGecko cho thông tin token..." />
		</div>
	),
};

export const NarrationNull: StoryObj<typeof LiveNarrationStream> = {
	render: () => <div className="p-4 text-xs text-muted-foreground">(null — renders nothing)</div>,
	args: { text: null },
};

// ─── SourceFaviconRiver ───────────────────────────────────────────────────────

const MOCK_SOURCES = [
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
	{
		domain: "gopluslabs.io",
		favicon: "https://icons.duckduckgo.com/ip3/gopluslabs.io.ico",
		url: "",
		dataType: "security",
	},
];

export const FaviconRiver: StoryObj<typeof SourceFaviconRiver> = {
	render: () => (
		<div className="max-w-sm p-4">
			<SourceFaviconRiver sources={MOCK_SOURCES} />
		</div>
	),
};

// ─── RateGateBanner ───────────────────────────────────────────────────────────

export const RateGate: StoryObj<typeof RateGateBanner> = {
	render: () => (
		<div className="max-w-sm p-4">
			<RateGateBanner latestGate={{ waitSeconds: 7.2, reason: "min_interval", ts: Date.now() }} />
		</div>
	),
};

// ─── ActivityTimeline ─────────────────────────────────────────────────────────

export const Timeline: StoryObj<typeof ActivityTimeline> = {
	render: () => (
		<div className="max-w-sm p-4">
			<ActivityTimeline
				spawnedAt={Date.now() - 30_000}
				rateGateWaits={[
					{ waitSeconds: 7.2, reason: "min_interval", ts: Date.now() - 20_000 },
					{ waitSeconds: 3.1, reason: "paced", ts: Date.now() - 10_000 },
				]}
			/>
		</div>
	),
};

// ─── AgentLane ────────────────────────────────────────────────────────────────

const MOCK_AGENT = {
	agentId: "tokenomics_analyst",
	agentName: "Tokenomics Analyst",
	agentType: "tokenomics",
	status: "running" as const,
	elapsedMs: 42_000,
	narrationHistory: [],
	currentNarration: "Supply 1B UNI, 85% circulating. Đang kiểm tra vesting schedule...",
	sourcesFetched: MOCK_SOURCES.slice(0, 2),
	factsCapturedCount: 12,
	modelAttribution: { model: "claude-sonnet-4-6", provider: "trollllm", tier: "standard" },
};

export const LaneRunning: StoryObj<typeof AgentLane> = {
	render: () => (
		<div className="max-w-xs p-4">
			<AgentLane agent={MOCK_AGENT} />
		</div>
	),
};

export const LaneDone: StoryObj<typeof AgentLane> = {
	render: () => (
		<div className="max-w-xs p-4">
			<AgentLane agent={{ ...MOCK_AGENT, status: "done", currentNarration: null }} />
		</div>
	),
};

export const LaneFailed: StoryObj<typeof AgentLane> = {
	render: () => (
		<div className="max-w-xs p-4">
			<AgentLane
				agent={{
					...MOCK_AGENT,
					status: "failed",
					currentNarration: null,
					failReason: "rate_limit",
					failMessage: "Provider quota exceeded",
				}}
			/>
		</div>
	),
};
