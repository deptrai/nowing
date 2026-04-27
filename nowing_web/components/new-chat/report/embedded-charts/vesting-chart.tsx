"use client";

import { useId } from "react";
import {
	Area,
	AreaChart,
	ReferenceLine,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";
import type { ChartSpec } from "./chart-spec";

export function VestingChart({ spec }: { spec: ChartSpec }) {
	const gradId = useId();
	const xKey = spec.xKey ?? "date";
	const yKey = spec.yKey ?? "supply";

	const fmt = (v: number) => {
		if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
		if (v >= 1e6) return `${(v / 1e6).toFixed(0)}M`;
		return String(v);
	};

	// Detect unlock cliff points (where supply jumps significantly)
	const cliffs: string[] = [];
	for (let i = 1; i < spec.data.length; i++) {
		const prev = Number(spec.data[i - 1]?.[yKey]) || 0;
		const curr = Number(spec.data[i]?.[yKey]) || 0;
		if (prev > 0 && (curr - prev) / prev > 0.05) {
			cliffs.push(String(spec.data[i]?.[xKey] ?? ""));
		}
	}

	return (
		<ResponsiveContainer width="100%" height={200}>
			<AreaChart data={spec.data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
				<defs>
					<linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
						<stop offset="5%" stopColor="var(--source-defillama)" stopOpacity={0.3} />
						<stop offset="95%" stopColor="var(--source-defillama)" stopOpacity={0} />
					</linearGradient>
				</defs>
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
					width={50}
				/>
				<Tooltip
					formatter={(v: number) => [fmt(v), spec.yLabel ?? "Supply"]}
					contentStyle={{
						background: "var(--card)",
						border: "1px solid var(--border)",
						borderRadius: 6,
						fontSize: 11,
					}}
				/>
				{cliffs.map((x) => (
					<ReferenceLine
						key={x}
						x={x}
						stroke="var(--crypto-neutral)"
						strokeDasharray="3 3"
						label={{ value: "unlock", fontSize: 9, fill: "var(--muted-foreground)" }}
					/>
				))}
				<Area
					type="monotone"
					dataKey={yKey}
					stroke="var(--source-defillama)"
					strokeWidth={2}
					fill={`url(#${gradId})`}
					dot={false}
				/>
			</AreaChart>
		</ResponsiveContainer>
	);
}
