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

function resolveCssVar(el: Element, varName: string): string {
	return getComputedStyle(el).getPropertyValue(varName).trim() || "#888";
}

export function PriceChart({ spec }: { spec: ChartSpec }) {
	const containerRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (!containerRef.current) return;
		let chart: { remove: () => void } | null = null;
		const el = containerRef.current;

		import("lightweight-charts").then(({ createChart, ColorType, LineStyle }) => {
			if (!el) return;

			// Canvas API cannot resolve CSS var() — must read computed values from DOM
			const textColor = resolveCssVar(el, "--muted-foreground");
			const borderColor = resolveCssVar(el, "--border");
			const gainColor = resolveCssVar(el, "--crypto-gain");
			const lossColor = resolveCssVar(el, "--crypto-loss");
			const lineColor = resolveCssVar(el, "--source-coingecko");

			chart = createChart(el, {
				width: el.clientWidth,
				height: 200,
				layout: {
					background: { type: ColorType.Solid, color: "transparent" },
					textColor,
				},
				grid: {
					vertLines: { color: borderColor, style: LineStyle.Dotted },
					horzLines: { color: borderColor, style: LineStyle.Dotted },
				},
				rightPriceScale: { borderVisible: false },
				timeScale: { borderVisible: false },
				crosshair: { vertLine: { labelVisible: false } },
			});

			const data = spec.data as PricePoint[];
			const hasOHLC = data[0]?.open !== undefined;

			if (hasOHLC) {
				const series = chart.addCandlestickSeries({
					upColor: gainColor,
					downColor: lossColor,
					borderUpColor: gainColor,
					borderDownColor: lossColor,
					wickUpColor: gainColor,
					wickDownColor: lossColor,
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
					color: lineColor,
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
