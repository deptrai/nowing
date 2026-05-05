// Story 10.1.4: cohort taxonomy colors. Shared by SankeyFlowChart (node fills)
// and SankeyLegend (color swatches) so the two components stay in sync.

import type { WalletCohort } from "@/lib/chat/streaming-state";

export const COHORT_COLORS: Record<WalletCohort, string> = {
	// Spec AC2:
	// - smart_money: green (signal — alpha money accumulating/distributing)
	// - cex: orange (volume noise — exchange flows)
	// - dex: blue (volume noise — AMM pass-through)
	// - retail: gray (background activity)
	// - insider: red (critical — supply unlocks / team movement)
	// - unknown: light-gray (no classification signal)
	smart_money: "#22c55e",
	cex: "#f97316",
	dex: "#3b82f6",
	retail: "#6b7280",
	insider: "#ef4444",
	unknown: "#9ca3af",
};

export const COHORT_LABELS: Record<WalletCohort, string> = {
	smart_money: "Smart Money",
	cex: "CEX",
	dex: "DEX",
	retail: "Retail",
	insider: "Insider",
	unknown: "Unknown",
};

export const COHORT_DESCRIPTIONS: Record<WalletCohort, string> = {
	smart_money: "Funds, alpha wallets — high-signal accumulation/distribution",
	cex: "Centralized exchange hot/cold wallets — volume noise",
	dex: "DEX routers, AMM pools — pass-through volume",
	retail: "Small wallets, no labels — background activity",
	insider: "Team, treasury, vesting contracts — supply unlock signal",
	unknown: "Unclassified labels",
};

// Display order for legend rendering — most-significant cohort first.
export const COHORT_DISPLAY_ORDER: readonly WalletCohort[] = [
	"smart_money",
	"insider",
	"cex",
	"dex",
	"retail",
	"unknown",
];

export function colorForCohort(cohort: WalletCohort | undefined | null): string {
	if (!cohort) return COHORT_COLORS.unknown;
	return COHORT_COLORS[cohort] ?? COHORT_COLORS.unknown;
}
