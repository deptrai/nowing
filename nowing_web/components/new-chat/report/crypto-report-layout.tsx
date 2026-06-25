"use client";

import { useAuiState } from "@assistant-ui/react";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { memo, useCallback, useMemo, useState } from "react";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import { StaticMarkdown } from "@/components/assistant-ui/static-markdown";
import { CryptoCitationProvider } from "./crypto-citation-context";
import type { CryptoDataCitation } from "@/components/tool-ui/citation/schema";
import type { TokenInsightRating } from "./token-hero-card";
import { getBearerToken } from "@/lib/auth-utils";
import { useScenarioResynthesize } from "@/lib/chat/use-scenario-resynthesize";
import { ProContentGate } from "@/components/crypto/ProContentGate";
import { useSubscriptionGate } from "@/hooks/use-subscription-gate";
import type {
	ScenarioType,
	ScenarioAssumptions,
} from "@/components/new-chat/simulator/scenario-simulator-panel";

const TokenHeroCard = dynamic(() => import("./token-hero-card").then((m) => m.TokenHeroCard), {
	ssr: false,
});
const ReportTOC = dynamic(() => import("./report-toc").then((m) => m.ReportTOC), { ssr: false });
const SourceDetailPanel = dynamic(
	() => import("./source-detail-panel").then((m) => m.SourceDetailPanel),
	{ ssr: false }
);
const NextActionBar = dynamic(() => import("./next-action-bar").then((m) => m.NextActionBar), {
	ssr: false,
});
const FollowUpChips = dynamic(() => import("./follow-up-chips").then((m) => m.FollowUpChips), {
	ssr: false,
});
const ScenarioSimulatorPanel = dynamic(
	() => import("../simulator/scenario-simulator-panel").then((m) => m.ScenarioSimulatorPanel),
	{ ssr: false }
);
const CoinComparisonOverlay = dynamic(
	() => import("../compare/coin-comparison-overlay").then((m) => m.CoinComparisonOverlay),
	{ ssr: false }
);
const SankeyFlowChart = dynamic(
	() => import("@/components/crypto/SankeyFlowChart").then((m) => m.SankeyFlowChart),
	{
		ssr: false,
		loading: () => <div className="h-[400px] w-full animate-pulse bg-muted/20 rounded-xl" />,
	}
);
const SankeyLegend = dynamic(
	() => import("@/components/crypto/SankeyLegend").then((m) => m.SankeyLegend),
	{ ssr: false }
);

const SENTINEL = "<!-- crypto-report-v2 -->";

type WalletCohort = "smart_money" | "cex" | "dex" | "retail" | "insider" | "unknown";

interface CohortSummaryEntry {
	count: number;
	net_flow_usd: number;
}

interface SankeyNode {
	id: string;
	cohort?: WalletCohort;
}

interface SankeyLink {
	source: string;
	target: string;
	value: number;
}

interface SmartMoneyFlowData {
	nodes: SankeyNode[];
	links: SankeyLink[];
	net_flow_amount: number;
	currency: string;
	source_domain?: string;
	cohort_summary?: Partial<Record<WalletCohort, CohortSummaryEntry>>;
}

function EmptySmartMoneyState({ sourceDomain }: { sourceDomain?: string }) {
	return (
		<div className="rounded-xl border border-border/40 bg-muted/10 p-8 text-center">
			<div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-muted/30">
				<svg
					xmlns="http://www.w3.org/2000/svg"
					width="24"
					height="24"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					strokeWidth="2"
					strokeLinecap="round"
					strokeLinejoin="round"
					className="text-muted-foreground"
				>
					<path d="M3 7c2 0 3 2 6 2s4-2 6-2 4 2 6 2" />
					<path d="M3 12c2 0 3 2 6 2s4-2 6-2 4 2 6 2" />
					<path d="M3 17c2 0 3 2 6 2s4-2 6-2 4 2 6 2" />
				</svg>
			</div>
			<h4 className="mb-1 text-sm font-semibold text-foreground">No labeled smart money flow</h4>
			<p className="mx-auto max-w-md text-xs text-muted-foreground">
				No labeled smart-money inflows/outflows for this token on Ethereum. Activity may be
				primarily on another chain (e.g., BNB Chain for CAKE, Solana for SOL-native tokens).
			</p>
			{sourceDomain && (
				<p className="mt-2 text-[10px] uppercase tracking-wide text-muted-foreground/70">
					source: {sourceDomain}
				</p>
			)}
		</div>
	);
}

interface CryptoReportMeta {
	report_type?: string;
	citation_map?: Record<string, unknown>;
	token_symbol?: string;
	token_name?: string;
	coingecko_id?: string;
	follow_ups?: string[];
	thread_id?: number;
	smart_money_flow?: SmartMoneyFlowData;
}

function isCryptoReport(text: string, meta: CryptoReportMeta | null): boolean {
	if (meta?.report_type === "comprehensive_crypto") return true;
	// Standalone smart money flow queries don't carry report_type or sentinel,
	// but still need the crypto layout to host the Sankey chart. Other sections
	// (TokenHero, TOC, etc.) are independently conditional and skip cleanly when
	// their data is absent — so this path produces a minimal layout, not noise.
	if (meta?.smart_money_flow) return true;
	return text.includes(SENTINEL);
}

/**
 * Extracts token symbol and name from crypto report heading when metadata
 * is unavailable (e.g. after page reload — DB has no metadata column).
 * Matches patterns like: "— LDO Token (Lido DAO)"
 */
function parseTokenFromReportText(text: string): { symbol: string; name: string } | null {
	const m = text.match(/—\s*([A-Z]{2,12})\s+Token[^(]*\(([^)]+)\)/);
	if (m) return { symbol: m[1], name: m[2] };
	// Fallback: "— SYMBOL Token" without name in parens
	const m2 = text.match(/—\s*([A-Z]{2,12})\s+Token\b/);
	if (m2) return { symbol: m2[1], name: "" };
	return null;
}

const CryptoReportLayoutImpl = () => {
	const text = useAuiState(({ message }) => {
		const parts =
			(message as unknown as { content?: { type: string; text?: string }[] })?.content ?? [];
		return parts.find((p) => p.type === "text")?.text ?? "";
	});
	const meta = useAuiState(
		({ message }) =>
			((message as { metadata?: { custom?: unknown } })?.metadata
				?.custom as CryptoReportMeta | null) ?? null
	);

	console.log("CryptoReportLayoutImpl meta keys:", JSON.stringify(meta ? Object.keys(meta) : null));

	const [selectedCitation, setSelectedCitation] = useState<CryptoDataCitation | null>(null);
	const [panelOpen, setPanelOpen] = useState(false);
	const [compareOpen, setCompareOpen] = useState(false);

	// Simulator state lifted here so both mobile + desktop instances stay in sync
	const [simSelectedScenario, setSimSelectedScenario] = useState<ScenarioType>("base");
	const [simAssumptions, setSimAssumptions] = useState<ScenarioAssumptions>({});
	const [simAssumptionsChanged, setSimAssumptionsChanged] = useState(false);

	const DEFAULT_ASSUMPTIONS_MAP: Record<ScenarioType, ScenarioAssumptions> = useMemo(
		() => ({
			base: {},
			bull: { btc_shock: 0.5, eth_shock: 0.4, competitor_growth: -0.2 },
			bear: { btc_shock: -0.4, eth_shock: -0.35, regulatory_adverse: true },
			stress: {
				btc_shock: -0.5,
				eth_shock: -0.5,
				tvl_shock: -0.5,
				regulatory_adverse: true,
				competitor_growth: 0.5,
			},
		}),
		[]
	);

	const handleSimScenarioSelect = useCallback(
		(s: ScenarioType) => {
			setSimSelectedScenario(s);
			setSimAssumptions(DEFAULT_ASSUMPTIONS_MAP[s]);
			setSimAssumptionsChanged(false);
		},
		[DEFAULT_ASSUMPTIONS_MAP]
	);

	const handleSimAssumptionChange = useCallback(
		(key: keyof ScenarioAssumptions, value: number | boolean) => {
			setSimAssumptions((prev) => ({ ...prev, [key]: value }));
			setSimAssumptionsChanged(true);
		},
		[]
	);

	const isCrypto = useMemo(() => isCryptoReport(text, meta), [text, meta]);

	// Parse token info from text when metadata not available (e.g. after page reload)
	const parsedToken = useMemo(
		() => (isCrypto && !meta?.token_symbol ? parseTokenFromReportText(text) : null),
		[isCrypto, meta?.token_symbol, text]
	);
	const tokenSymbol = meta?.token_symbol ?? parsedToken?.symbol;
	const tokenName = meta?.token_name ?? parsedToken?.name ?? "";

	const tokenInsightRating = useMemo((): TokenInsightRating | undefined => {
		const map = meta?.citation_map;
		if (!map) return undefined;
		for (const val of Object.values(map)) {
			const cite = val as Record<string, unknown>;
			if (cite?.provider === "tokeninsight" && cite?.raw_value) {
				const raw = cite.raw_value as Record<string, unknown>;
				if (raw.overall_rating && typeof raw.overall_score === "number") {
					return {
						overall_rating: raw.overall_rating as string,
						overall_score: raw.overall_score,
					};
				}
			}
		}
		return undefined;
	}, [meta?.citation_map]);

	const openCitation = useCallback((citation: CryptoDataCitation) => {
		setSelectedCitation(citation);
		setPanelOpen(true);
	}, []);

	// Fall back to URL param so ScenarioSimulator/Compare work after page reload
	const params = useParams();
	const urlThreadId = useMemo(() => {
		const raw = params?.chat_id;
		if (!raw) return null;
		const id = Number(Array.isArray(raw) ? raw[0] : raw);
		return Number.isFinite(id) ? id : null;
	}, [params?.chat_id]);
	const threadId = meta?.thread_id ?? urlThreadId;
	const token = getBearerToken();

	const { isPro: isProUser } = useSubscriptionGate();

	const { activeScenario, scenarioResult, isResynthesizing, resynthesize, resetToBase } =
		useScenarioResynthesize({ threadId, token });

	const handleResynthesize = useCallback(
		(scenario: ScenarioType, assumptions: ScenarioAssumptions) => {
			// Round-2 review: don't fire the LLM re-synthesize call for users
			// behind the paywall. The visual gate already blocks Tab focus, but
			// programmatic callers (or future bypasses) shouldn't burn backend
			// cost either.
			if (!isProUser) return;
			resynthesize(scenario, assumptions);
			setSimAssumptionsChanged(false);
		},
		[resynthesize, isProUser]
	);

	if (!isCrypto) return <MarkdownText />;

	const cleanText = text.replace(SENTINEL, "").trimStart();

	return (
		<CryptoCitationProvider
			citationMap={meta?.citation_map as Record<string, CryptoDataCitation> | undefined}
			onOpenCitation={openCitation}
		>
			<div className="relative flex gap-0 lg:gap-6" data-slot="crypto-report-layout">
				{/* Round-2 review: TOC also gated. The TOC enumerates every Pro-only
				    section heading and links straight into the (still-DOM) blurred
				    body, leaking the report's outline to free users. */}
				{isProUser ? <ReportTOC content={cleanText} className="hidden lg:block" /> : null}

				<div className="min-w-0 flex-1">
					<TokenHeroCard
						symbol={tokenSymbol}
						name={tokenName}
						coingeckoId={meta?.coingecko_id}
						reportText={cleanText}
						tokenInsightRating={tokenInsightRating}
					/>

					{/* Active scenario badge */}
					{activeScenario !== "base" && scenarioResult && (
						<div className="mt-3 flex items-center gap-2 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-xs">
							<span className="font-medium text-primary">
								Viewing:{" "}
								{
									{
										bull: "🚀 Bull Case",
										bear: "🐻 Bear Case",
										stress: "⚠️ Stress Test",
										base: "📊 Base Case",
									}[activeScenario]
								}
							</span>
							<button
								onClick={resetToBase}
								className="ml-auto text-muted-foreground hover:text-foreground underline"
							>
								View Base Case
							</button>
						</div>
					)}

					<div
						className="mt-4 transition-opacity duration-200"
						data-scenario={activeScenario !== "base" ? activeScenario : undefined}
					>
						<ProContentGate
							title="Deep Research Analysis"
							description="Upgrade to Pro to access our AI-powered deep research and comprehensive token analysis."
						>
							{activeScenario !== "base" && scenarioResult ? (
								<StaticMarkdown
									key={`scenario-${activeScenario}-${scenarioResult.loadedAt}`}
									content={scenarioResult.content}
								/>
							) : (
								<MarkdownText preprocessText={(t) => t.replace(SENTINEL, "").trimStart()} />
							)}
						</ProContentGate>
					</div>

					{meta?.smart_money_flow && Array.isArray(meta.smart_money_flow.nodes) && (
						<div className="mt-6">
							<ProContentGate
								title="Smart Money Flow"
								description="Visualize whale accumulation and distribution with Pro."
							>
								{Array.isArray(meta.smart_money_flow.links) &&
								meta.smart_money_flow.links.length > 0 ? (
									<>
										<SankeyFlowChart
											nodes={meta.smart_money_flow.nodes}
											links={meta.smart_money_flow.links}
											netFlowAmount={meta.smart_money_flow.net_flow_amount}
											currency={meta.smart_money_flow.currency}
											isLoading={false}
										/>
										<SankeyLegend
											cohortSummary={meta.smart_money_flow.cohort_summary}
											currency={meta.smart_money_flow.currency}
										/>
									</>
								) : (
									<EmptySmartMoneyState sourceDomain={meta.smart_money_flow.source_domain} />
								)}
							</ProContentGate>
						</div>
					)}

					<NextActionBar
						tokenSymbol={tokenSymbol}
						tokenName={tokenName}
						onOpenCompare={() => {
							if (!tokenSymbol) return;
							setCompareOpen(true);
						}}
						className="mt-6"
					/>

					<FollowUpChips followUps={meta?.follow_ups ?? []} className="mt-2" />

					{/* Scenario simulator stacks below report on screens < 2xl (mobile/tablet/laptop) */}
					{threadId && (
						<div className="mt-6 2xl:hidden">
							<ProContentGate
								title="Scenario Simulator"
								description="Upgrade to Pro to simulate Bull, Bear, and Stress scenarios for this token."
							>
								<ScenarioSimulatorPanel
									threadId={threadId}
									tokenName={tokenName}
									activeScenario={activeScenario}
									scenarioResult={scenarioResult}
									isResynthesizing={isResynthesizing}
									onResynthesize={handleResynthesize}
									onResetToBase={resetToBase}
									selectedScenario={simSelectedScenario}
									assumptions={simAssumptions}
									assumptionsChanged={simAssumptionsChanged}
									onScenarioSelect={handleSimScenarioSelect}
									onAssumptionChange={handleSimAssumptionChange}
								/>
							</ProContentGate>
						</div>
					)}
				</div>

				{/* Scenario simulator sticky-right on screens ≥ 2xl (≥1536px) */}
				{threadId && (
					<div className="hidden 2xl:block">
						<div className="sticky top-6 w-[300px]">
							<ProContentGate
								title="Scenario Simulator"
								description="Simulate Bull, Bear, and Stress scenarios with Pro."
							>
								<ScenarioSimulatorPanel
									threadId={threadId}
									tokenName={tokenName}
									activeScenario={activeScenario}
									scenarioResult={scenarioResult}
									isResynthesizing={isResynthesizing}
									onResynthesize={handleResynthesize}
									onResetToBase={resetToBase}
									selectedScenario={simSelectedScenario}
									assumptions={simAssumptions}
									assumptionsChanged={simAssumptionsChanged}
									onScenarioSelect={handleSimScenarioSelect}
									onAssumptionChange={handleSimAssumptionChange}
								/>
							</ProContentGate>
						</div>
					</div>
				)}
			</div>

			<SourceDetailPanel
				citation={selectedCitation}
				open={panelOpen}
				onClose={() => setPanelOpen(false)}
			/>

			<CoinComparisonOverlay
				open={compareOpen}
				onClose={() => setCompareOpen(false)}
				primaryToken={tokenSymbol ?? ""}
				primaryName={tokenName}
				primaryCoingeckoId={meta?.coingecko_id}
				token={token}
			/>
		</CryptoCitationProvider>
	);
};

export const CryptoReportLayout = memo(CryptoReportLayoutImpl);
