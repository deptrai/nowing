"use client";

import type {
	CohortSummaryEntry,
	SmartMoneyFlowData,
	WalletCohort,
} from "@/lib/chat/streaming-state";
import {
	COHORT_DESCRIPTIONS,
	COHORT_DISPLAY_ORDER,
	COHORT_LABELS,
	colorForCohort,
} from "./cohort-colors";

interface SankeyLegendProps {
	cohortSummary?: SmartMoneyFlowData["cohort_summary"];
	currency?: string;
	locale?: string;
}

function formatCompact(amount: number, locale: string, currency: string): string {
	if (!Number.isFinite(amount)) return "—";
	try {
		return new Intl.NumberFormat(locale, {
			style: "currency",
			currency,
			notation: "compact",
		}).format(amount);
	} catch {
		return new Intl.NumberFormat("en-US", {
			style: "currency",
			currency: "USD",
			notation: "compact",
		}).format(amount);
	}
}

/**
 * Story 10.1.4 AC5: legend showing cohort colors + per-cohort wallet count and
 * net flow. Always rendered alongside SankeyFlowChart so color-blind users
 * have a tabular reference and to expose the analytics layer that the visual
 * chart compresses ("smart money is accumulating, CEX is distributing").
 *
 * Renders nothing if cohortSummary is empty/undefined — caller can mount
 * unconditionally.
 */
export function SankeyLegend({
	cohortSummary,
	currency = "USD",
	locale = "en-US",
}: SankeyLegendProps) {
	if (!cohortSummary || Object.keys(cohortSummary).length === 0) {
		return null;
	}

	const entries: Array<{
		cohort: WalletCohort;
		entry: CohortSummaryEntry;
	}> = [];
	for (const cohort of COHORT_DISPLAY_ORDER) {
		const entry = cohortSummary[cohort];
		if (entry && entry.count > 0) {
			entries.push({ cohort, entry });
		}
	}
	if (entries.length === 0) return null;

	return (
		<div className="mt-3 flex flex-wrap gap-2 border-t border-border/40 pt-3">
			{entries.map(({ cohort, entry }) => {
				const flowColor =
					entry.net_flow_usd > 0
						? "text-green-500"
						: entry.net_flow_usd < 0
							? "text-red-500"
							: "text-muted-foreground";
				const sign = entry.net_flow_usd > 0 ? "+" : "";
				return (
					<div
						key={cohort}
						title={COHORT_DESCRIPTIONS[cohort]}
						className="flex items-center gap-2 rounded-md border border-border/40 bg-muted/10 px-2.5 py-1.5 text-xs"
					>
						<span
							aria-hidden
							className="inline-block h-2.5 w-2.5 rounded-full"
							style={{ backgroundColor: colorForCohort(cohort) }}
						/>
						<span className="font-medium text-foreground">{COHORT_LABELS[cohort]}</span>
						<span className="text-muted-foreground">
							{entry.count} wallet{entry.count > 1 ? "s" : ""}
						</span>
						<span className={`font-mono ${flowColor}`}>
							{sign}
							{formatCompact(entry.net_flow_usd, locale, currency)}
						</span>
					</div>
				);
			})}
		</div>
	);
}
