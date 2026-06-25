"use client";

import dynamic from "next/dynamic";
import { memo } from "react";
import { parseChartSpec } from "./chart-spec";

const PriceChart = dynamic(() => import("./price-chart").then((m) => m.PriceChart), {
	ssr: false,
	loading: () => <ChartSkeleton />,
});
const TvlChart = dynamic(() => import("./tvl-chart").then((m) => m.TvlChart), {
	ssr: false,
	loading: () => <ChartSkeleton />,
});
const HolderPie = dynamic(() => import("./holder-pie").then((m) => m.HolderPie), {
	ssr: false,
	loading: () => <ChartSkeleton />,
});
const YieldBars = dynamic(() => import("./yield-bars").then((m) => m.YieldBars), {
	ssr: false,
	loading: () => <ChartSkeleton />,
});
const VestingChart = dynamic(() => import("./vesting-chart").then((m) => m.VestingChart), {
	ssr: false,
	loading: () => <ChartSkeleton />,
});

function ChartSkeleton() {
	return (
		<div className="my-4 h-[200px] w-full animate-pulse rounded-lg bg-muted" aria-hidden="true" />
	);
}

interface EmbeddedChartWrapperProps {
	chartId: string;
	spec: string;
}

function EmbeddedChartWrapperImpl({ chartId, spec: specStr }: EmbeddedChartWrapperProps) {
	const spec = parseChartSpec(specStr);
	if (!spec) return null;

	const chartType = spec.type;
	// Fallback: infer from chartId suffix if type not set
	const effectiveType = chartType ?? (chartId.includes("tvl") ? "line" : "bar");

	const source = spec.source ?? "";

	return (
		<div
			className="my-4 overflow-hidden rounded-lg border border-border/60 bg-card/50 p-3"
			data-slot="embedded-chart"
			data-chart-id={chartId}
			data-chart-type={effectiveType}
		>
			{effectiveType === "candle" ? (
				<PriceChart spec={spec} />
			) : effectiveType === "pie" ? (
				<HolderPie spec={spec} />
			) : effectiveType === "bar" ? (
				<YieldBars spec={spec} />
			) : effectiveType === "area" ? (
				<VestingChart spec={spec} />
			) : effectiveType === "line" && (source === "coingecko" || chartId.startsWith("price-")) ? (
				<PriceChart spec={spec} />
			) : (
				<TvlChart spec={spec} />
			)}
			{source && (
				<p className="mt-1 text-right text-[10px] text-muted-foreground/60">Source: {source}</p>
			)}
		</div>
	);
}

export const EmbeddedChartWrapper = memo(EmbeddedChartWrapperImpl);
