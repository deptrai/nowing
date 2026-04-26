"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ChartSpec } from "./chart-spec";

export function TvlChart({ spec }: { spec: ChartSpec }) {
	const xKey = spec.xKey ?? "date";
	const yKey = spec.yKey ?? "tvlUsd";

	const fmt = (v: number) => {
		if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
		if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
		return `$${v}`;
	};

	return (
		<ResponsiveContainer width="100%" height={200}>
			<LineChart data={spec.data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
				<XAxis
					dataKey={xKey}
					tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
					tickLine={false}
					axisLine={false}
				/>
				<YAxis
					tickFormatter={fmt}
					tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
					tickLine={false}
					axisLine={false}
					width={56}
				/>
				<Tooltip
					formatter={(v: number) => [fmt(v), "TVL"]}
					contentStyle={{
						background: "var(--card)",
						border: "1px solid var(--border)",
						borderRadius: 6,
						fontSize: 11,
					}}
				/>
				<Line
					type="monotone"
					dataKey={yKey}
					stroke="var(--source-defillama)"
					strokeWidth={2}
					dot={false}
				/>
			</LineChart>
		</ResponsiveContainer>
	);
}
