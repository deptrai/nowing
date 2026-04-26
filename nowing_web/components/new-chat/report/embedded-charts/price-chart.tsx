"use client";

import { useEffect, useRef } from "react";
import type { ChartSpec } from "./chart-spec";

// Lightweight Charts (TradingView) — candle/line price chart
// Dynamic import to avoid SSR issues (handled at wrapper level via next/dynamic)

interface PricePoint {
	time: string | number;
	open?: number;
	high?: number;
	low?: number;
	close?: number;
	value?: number;
}

export function PriceChart({ spec }: { spec: ChartSpec }) {
	const containerRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (!containerRef.current) return;
		let chart: { remove: () => void } | null = null;

		import("lightweight-charts").then(({ createChart, ColorType, LineStyle }) => {
			if (!containerRef.current) return;

			chart = createChart(containerRef.current, {
				width: containerRef.current.clientWidth,
				height: 200,
				layout: {
					background: { type: ColorType.Solid, color: "transparent" },
					textColor: "var(--muted-foreground)",
				},
				grid: {
					vertLines: { color: "var(--border)", style: LineStyle.Dotted },
					horzLines: { color: "var(--border)", style: LineStyle.Dotted },
				},
				rightPriceScale: { borderVisible: false },
				timeScale: { borderVisible: false },
				crosshair: { vertLine: { labelVisible: false } },
			});

			const data = spec.data as PricePoint[];
			const hasOHLC = data[0]?.open !== undefined;

			if (hasOHLC) {
				const series = chart.addCandlestickSeries({
					upColor: "var(--crypto-gain)",
					downColor: "var(--crypto-loss)",
					borderUpColor: "var(--crypto-gain)",
					borderDownColor: "var(--crypto-loss)",
					wickUpColor: "var(--crypto-gain)",
					wickDownColor: "var(--crypto-loss)",
				});
				series.setData(
					data.map((d) => ({
						time: d.time as string,
						open: d.open!,
						high: d.high!,
						low: d.low!,
						close: d.close!,
					}))
				);
			} else {
				const series = chart.addLineSeries({
					color: "var(--source-coingecko)",
					lineWidth: 2,
				});
				series.setData(
					data.map((d) => ({
						time: d.time as string,
						value: d.value ?? d.close ?? 0,
					}))
				);
			}

			chart.timeScale().fitContent();
		});

		return () => chart?.remove();
	}, [spec]);

	return <div ref={containerRef} className="w-full" style={{ height: 200 }} />;
}
