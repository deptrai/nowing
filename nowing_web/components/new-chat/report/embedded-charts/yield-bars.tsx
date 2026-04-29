"use client";

import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ChartSpec } from "./chart-spec";

export function YieldBars({ spec }: { spec: ChartSpec }) {
	const xKey = spec.xKey ?? "name";
	const yKey = spec.yKey ?? "apy";

	return (
		<ResponsiveContainer width="100%" height={200}>
			<BarChart data={spec.data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
				<XAxis
					dataKey={xKey}
					tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
					tickLine={false}
					axisLine={false}
				/>
				<YAxis
					tickFormatter={(v) => `${v}%`}
					tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
					tickLine={false}
					axisLine={false}
					width={40}
				/>
				<Tooltip
					formatter={(v: number) => [`${v}%`, "APY"]}
					contentStyle={{
						background: "var(--card)",
						border: "1px solid var(--border)",
						borderRadius: 6,
						fontSize: 11,
					}}
				/>
				<Bar dataKey={yKey} radius={[3, 3, 0, 0]}>
					{spec.data.map((_, i) => (
						<Cell
							key={i}
							fill={i % 2 === 0 ? "var(--source-defillama)" : "var(--source-coingecko)"}
						/>
					))}
				</Bar>
			</BarChart>
		</ResponsiveContainer>
	);
}
