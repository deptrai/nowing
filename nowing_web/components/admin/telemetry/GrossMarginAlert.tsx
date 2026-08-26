"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
	CartesianGrid,
	Legend,
	Line,
	LineChart,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";
import {
	adminTelemetryApiService,
	type GrossMarginSummary,
} from "@/lib/apis/admin-telemetry-api.service";

const WINDOW_OPTIONS = [
	{ label: "1h", value: 1 },
	{ label: "6h", value: 6 },
	{ label: "24h", value: 24 },
	{ label: "7d", value: 168 },
	{ label: "30d", value: 720 },
] as const;

const LOW_MARGIN_THRESHOLD = 0.15;

interface GrossMarginAlertProps {
	tick?: number;
}

function formatPercent(value: number | null) {
	if (value === null || value === undefined) return "N/A";
	return `${(value * 100).toFixed(2)}%`;
}

export default function GrossMarginAlert({ tick }: GrossMarginAlertProps) {
	const [windowHours, setWindowHours] = useState<number>(24);
	const [data, setData] = useState<GrossMarginSummary | null>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const load = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const d = await adminTelemetryApiService.grossMargin({
				window_hours: windowHours as 1 | 6 | 24 | 168 | 720,
			});
			setData(d);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to load gross margin");
		} finally {
			setLoading(false);
		}
	}, [windowHours]);

	// biome-ignore lint/correctness/useExhaustiveDependencies: tick is the auto-refresh trigger
	useEffect(() => {
		void load();
	}, [load, tick]);

	const alert = useMemo(() => {
		if (!data) return null;
		const margin = data.overall_gross_margin;
		if (margin === null || margin === undefined)
			return { text: "N/A", color: "bg-slate-100 text-slate-600" };
		if (margin < 0)
			return { text: `Negative margin ${formatPercent(margin)}`, color: "bg-red-100 text-red-700" };
		if (margin < LOW_MARGIN_THRESHOLD)
			return { text: `Low margin ${formatPercent(margin)}`, color: "bg-amber-100 text-amber-700" };
		return { text: `Margin ${formatPercent(margin)}`, color: "bg-green-100 text-green-700" };
	}, [data]);

	return (
		<div className="space-y-4 rounded border p-4">
			<div className="flex flex-wrap items-end gap-3">
				<h3 className="text-lg font-semibold">Gross Margin</h3>
				<select
					className="h-9 rounded border px-2 text-sm"
					value={windowHours}
					onChange={(e) => setWindowHours(parseInt(e.target.value, 10))}
				>
					{WINDOW_OPTIONS.map((w) => (
						<option key={w.value} value={w.value}>
							{w.label}
						</option>
					))}
				</select>
				<button
					type="button"
					onClick={load}
					className="h-9 rounded border bg-slate-100 px-3 text-sm hover:bg-slate-200"
				>
					Refresh
				</button>
			</div>

			{loading && <div className="text-sm text-slate-500">Loading...</div>}
			{error && (
				<div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
					{error}
				</div>
			)}

			{data && (
				<>
					<div className="grid grid-cols-4 gap-4">
						<div className="rounded border p-3">
							<div className="text-xs text-slate-500">Revenue</div>
							<div className="font-mono text-lg font-semibold">
								${(data.total_revenue_micros / 1_000_000).toFixed(2)}
							</div>
						</div>
						<div className="rounded border p-3">
							<div className="text-xs text-slate-500">COGS</div>
							<div className="font-mono text-lg font-semibold">
								${(data.total_cogs_micros / 1_000_000).toFixed(2)}
							</div>
						</div>
						<div className="rounded border p-3">
							<div className="text-xs text-slate-500">Non-LLM Cost</div>
							<div className="font-mono text-lg font-semibold">
								${(data.non_llm_cost_micros / 1_000_000).toFixed(2)}
							</div>
						</div>
						<div className="rounded border p-3">
							<div className="text-xs text-slate-500">Overall Margin</div>
							<div className="font-mono text-lg font-semibold">
								{formatPercent(data.overall_gross_margin)}
							</div>
						</div>
					</div>

					{alert && (
						<div
							className={`inline-flex items-center gap-2 rounded px-3 py-2 text-sm font-medium ${alert.color}`}
						>
							{alert.text}
							{data.worst_workspace_id !== null && data.worst_workspace_margin !== null && (
								<span className="font-mono text-xs">
									worst: ws {data.worst_workspace_id} ({formatPercent(data.worst_workspace_margin)})
								</span>
							)}
							{data.worst_model !== null && data.worst_model !== undefined && (
								<span className="font-mono text-xs">worst model: {data.worst_model}</span>
							)}
						</div>
					)}

					<div className="h-64 rounded border p-2">
						<ResponsiveContainer width="100%" height="100%">
							<LineChart data={data.points}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis dataKey="period" tick={{ fontSize: 10 }} />
								<YAxis tickFormatter={(v) => formatPercent(v as number)} tick={{ fontSize: 10 }} />
								<Tooltip />
								<Legend />
								<Line type="monotone" dataKey="gross_margin" name="Gross margin" stroke="#8884d8" />
							</LineChart>
						</ResponsiveContainer>
					</div>
				</>
			)}
		</div>
	);
}
