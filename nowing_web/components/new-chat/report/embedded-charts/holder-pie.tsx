"use client";

import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { ChartSpec } from "./chart-spec";

const COLORS = [
	"var(--source-defillama)",
	"var(--source-coingecko)",
	"var(--source-goplus)",
	"var(--source-etherscan)",
	"var(--source-dexscreener)",
	"oklch(0.6 0.15 320)",
];

export function HolderPie({ spec }: { spec: ChartSpec }) {
	const nameKey = spec.nameKey ?? "name";
	const valueKey = spec.valueKey ?? "value";

	return (
		<ResponsiveContainer width="100%" height={220}>
			<PieChart>
				<Pie
					data={spec.data}
					dataKey={valueKey}
					nameKey={nameKey}
					cx="50%"
					cy="45%"
					outerRadius={80}
					label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(1)}%`}
					labelLine={false}
				>
					{spec.data.map((_, i) => (
						<Cell key={i} fill={COLORS[i % COLORS.length]} />
					))}
				</Pie>
				<Tooltip
					formatter={(v: number) => [v <= 100 ? `${v}%` : v.toLocaleString(), ""]}
					contentStyle={{
						background: "var(--card)",
						border: "1px solid var(--border)",
						borderRadius: 6,
						fontSize: 11,
					}}
				/>
				<Legend wrapperStyle={{ fontSize: 11 }} />
			</PieChart>
		</ResponsiveContainer>
	);
}
