"use client";

import {
	Bar,
	CartesianGrid,
	ComposedChart,
	Line,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import type { UsageTimeSeriesPoint } from "@/contracts/types/usage.types";

interface UsageChartProps {
	data: UsageTimeSeriesPoint[];
	isLoading: boolean;
}

function formatUsdMicros(micros: number): string {
	const dollars = micros / 1_000_000;
	if (dollars >= 1) return `$${dollars.toFixed(2)}`;
	if (dollars > 0) return `$${dollars.toFixed(3)}`;
	return "$0";
}

export function UsageChart({ data, isLoading }: UsageChartProps) {
	if (isLoading) {
		return <Skeleton className="h-[240px] w-full" />;
	}

	if (data.length === 0) {
		return (
			<div className="flex h-[240px] items-center justify-center rounded-md border border-dashed">
				<p className="text-sm text-muted-foreground">No data for selected range</p>
			</div>
		);
	}

	return (
		<div data-testid="usage-chart" className="h-[240px] w-full">
			<ResponsiveContainer width="100%" height="100%">
				<ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
					<CartesianGrid strokeDasharray="3 3" vertical={false} />
					<XAxis dataKey="period" tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
					<YAxis
						yAxisId="left"
						tick={{ fontSize: 12 }}
						tickLine={false}
						axisLine={false}
						tickFormatter={(value: number) => formatUsdMicros(value)}
						width={60}
					/>
					<YAxis
						yAxisId="right"
						orientation="right"
						tick={{ fontSize: 12 }}
						tickLine={false}
						axisLine={false}
						tickFormatter={(value: number) => value.toLocaleString()}
						width={60}
					/>
					<Tooltip
						formatter={(value, name) => {
							const numericValue = typeof value === "number" ? value : 0;
							const label = name === "cost_micros" ? "Cost" : "Tokens";
							const display =
								name === "cost_micros"
									? formatUsdMicros(numericValue)
									: numericValue.toLocaleString();
							return [display, label];
						}}
						labelFormatter={(label) => `Period: ${String(label)}`}
					/>
					<Bar
						yAxisId="left"
						dataKey="cost_micros"
						fill="hsl(var(--primary))"
						radius={[4, 4, 0, 0]}
					/>
					<Line
						yAxisId="right"
						type="monotone"
						dataKey="total_tokens"
						stroke="hsl(var(--chart-2, 142 76% 36%))"
						strokeWidth={2}
						dot={false}
					/>
				</ComposedChart>
			</ResponsiveContainer>
		</div>
	);
}
