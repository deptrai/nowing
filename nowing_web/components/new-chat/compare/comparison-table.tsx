"use client";

import { cn } from "@/lib/utils";
import { StaticMarkdown } from "@/components/assistant-ui/static-markdown";

interface ComparisonTableProps {
	primarySymbol: string;
	secondarySymbol: string;
	primaryData: Record<string, unknown>;
	secondaryData: Record<string, unknown>;
	verdict: string;
	verdictLoading: boolean;
	className?: string;
}

function fmt(val: unknown, isCurrency = false, isPercent = false): string {
	if (val === null || val === undefined) return "—";
	const n = Number(val);
	if (Number.isNaN(n) || !Number.isFinite(n)) return "—";
	if (isPercent) return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
	const prefix = isCurrency ? "$" : "";
	const abs = Math.abs(n);
	if (abs >= 1e15) return `${prefix}${n.toExponential(2)}`;
	if (abs >= 1e12) return `${prefix}${(n / 1e12).toFixed(2)}T`;
	if (abs >= 1e9) return `${prefix}${(n / 1e9).toFixed(2)}B`;
	if (abs >= 1e6) return `${prefix}${(n / 1e6).toFixed(2)}M`;
	if (abs >= 1e3) return `${prefix}${(n / 1e3).toFixed(2)}K`;
	if (isCurrency && abs > 0 && abs < 1) return `$${n.toFixed(6)}`;
	return `${prefix}${n.toFixed(2)}`;
}

type Comparison = "better" | "worse" | "neutral";

function compareValues(
	primary: unknown,
	secondary: unknown,
	higherIsBetter: boolean
): [Comparison, Comparison] {
	const aMissing = primary === null || primary === undefined;
	const bMissing = secondary === null || secondary === undefined;
	// One-sided data: highlight the side with data
	if (aMissing && !bMissing) return ["neutral", "better"];
	if (!aMissing && bMissing) return ["better", "neutral"];
	const a = Number(primary);
	const b = Number(secondary);
	if (Number.isNaN(a) || Number.isNaN(b) || a === b) return ["neutral", "neutral"];
	if (higherIsBetter) {
		return a > b ? ["better", "worse"] : ["worse", "better"];
	}
	return a < b ? ["better", "worse"] : ["worse", "better"];
}

function Cell({ value, comparison }: { value: string; comparison: Comparison }) {
	return (
		<td
			className={cn(
				"px-4 py-2.5 text-sm text-center tabular-nums",
				comparison === "better" && "text-green-600 dark:text-green-400 font-medium",
				comparison === "worse" && "text-red-500 dark:text-red-400"
			)}
		>
			{value}
		</td>
	);
}

const ROWS: {
	label: string;
	key: string;
	isCurrency?: boolean;
	isPercent?: boolean;
	higherIsBetter?: boolean;
}[] = [
	{ label: "Price", key: "current_price_usd", isCurrency: true, higherIsBetter: false },
	{ label: "Market Cap", key: "market_cap", isCurrency: true, higherIsBetter: true },
	{ label: "24h Volume", key: "total_volume_24h", isCurrency: true, higherIsBetter: true },
	{ label: "24h Change", key: "price_change_24h_pct", isPercent: true, higherIsBetter: true },
	{ label: "7d Change", key: "price_change_7d_pct", isPercent: true, higherIsBetter: true },
	{ label: "30d Change", key: "price_change_30d_pct", isPercent: true, higherIsBetter: true },
	{ label: "TVL", key: "tvl", isCurrency: true, higherIsBetter: true },
	{ label: "Circ. Supply", key: "circulating_supply", higherIsBetter: false },
	{ label: "Max Supply", key: "max_supply", higherIsBetter: false },
	{ label: "ATH", key: "ath_usd", isCurrency: true, higherIsBetter: true },
];

function VerdictBox({
	verdict,
	loading,
	primarySymbol,
	secondarySymbol,
}: {
	verdict: string;
	loading: boolean;
	primarySymbol: string;
	secondarySymbol: string;
}) {
	if (!verdict && !loading) return null;

	return (
		<div className="mt-6 rounded-xl border bg-muted/30 p-4" data-slot="verdict-box">
			<p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
				AI Verdict — {primarySymbol} vs {secondarySymbol}
			</p>
			{verdict ? (
				<StaticMarkdown content={verdict} className="text-sm" />
			) : (
				<div className="flex items-center gap-2 text-sm text-muted-foreground">
					<div className="size-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
					Synthesizing verdict…
				</div>
			)}
		</div>
	);
}

export function ComparisonTable({
	primarySymbol,
	secondarySymbol,
	primaryData,
	secondaryData,
	verdict,
	verdictLoading,
	className,
}: ComparisonTableProps) {
	return (
		<div className={cn("flex flex-col gap-0", className)} data-slot="comparison-table">
			<div className="overflow-hidden rounded-xl border">
				<table className="w-full text-left">
					<thead>
						<tr className="border-b bg-muted/50">
							<th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide w-1/3">
								Metric
							</th>
							<th className="px-4 py-2.5 text-xs font-semibold text-center uppercase tracking-wide w-1/3">
								{primarySymbol}
							</th>
							<th className="px-4 py-2.5 text-xs font-semibold text-center uppercase tracking-wide w-1/3">
								{secondarySymbol}
							</th>
						</tr>
					</thead>
					<tbody className="divide-y">
						{ROWS.map((row) => {
							const pVal = primaryData[row.key];
							const sVal = secondaryData[row.key];
							// Skip rows where both values are missing
							if ((pVal === null || pVal === undefined) && (sVal === null || sVal === undefined)) {
								return null;
							}
							const [pComp, sComp] = compareValues(pVal, sVal, row.higherIsBetter ?? false);
							return (
								<tr key={row.key} className="hover:bg-muted/30 transition-colors">
									<td className="px-4 py-2.5 text-sm text-muted-foreground">{row.label}</td>
									<Cell value={fmt(pVal, row.isCurrency, row.isPercent)} comparison={pComp} />
									<Cell value={fmt(sVal, row.isCurrency, row.isPercent)} comparison={sComp} />
								</tr>
							);
						})}
					</tbody>
				</table>
			</div>

			<VerdictBox
				verdict={verdict}
				loading={verdictLoading}
				primarySymbol={primarySymbol}
				secondarySymbol={secondarySymbol}
			/>
		</div>
	);
}
