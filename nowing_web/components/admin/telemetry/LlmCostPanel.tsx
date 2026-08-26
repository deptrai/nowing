"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
	Bar,
	BarChart,
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
	type LlmCostBreakdown,
} from "@/lib/apis/admin-telemetry-api.service";

const WINDOW_OPTIONS = [
	{ label: "1h", value: 1 },
	{ label: "6h", value: 6 },
	{ label: "24h", value: 24 },
	{ label: "7d", value: 168 },
	{ label: "30d", value: 720 },
] as const;

const PROVIDER_OPTIONS = ["", "openai", "anthropic", "google", "deepseek", "unknown"];

function formatMicros(micros: number): string {
	return `$${(micros / 1_000_000).toFixed(4)}`;
}

interface LlmCostPanelProps {
	tick?: number;
}

export default function LlmCostPanel({ tick }: LlmCostPanelProps) {
	const [windowHours, setWindowHours] = useState<number>(24);
	const [provider, setProvider] = useState<string>("");
	const [workspaceId, setWorkspaceId] = useState<string>("");
	const [data, setData] = useState<LlmCostBreakdown | null>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const load = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const parsed = workspaceId ? parseInt(workspaceId, 10) : NaN;
			const workspace_id = Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
			const d = await adminTelemetryApiService.llmCost({
				window_hours: windowHours as 1 | 6 | 24 | 168 | 720,
				provider: provider || undefined,
				workspace_id,
			});
			setData(d);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to load LLM cost");
		} finally {
			setLoading(false);
		}
	}, [windowHours, provider, workspaceId]);

	// biome-ignore lint/correctness/useExhaustiveDependencies: tick is the auto-refresh trigger
	useEffect(() => {
		void load();
	}, [load, tick]);

	const chartData = useMemo(() => data?.time_series ?? [], [data]);

	return (
		<div className="space-y-4 rounded border p-4">
			<div className="flex flex-wrap items-end gap-3">
				<div>
					<div className="mb-1 text-xs text-slate-500">Window</div>
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
				</div>
				<div>
					<div className="mb-1 text-xs text-slate-500">Provider</div>
					<select
						className="h-9 rounded border px-2 text-sm"
						value={provider}
						onChange={(e) => setProvider(e.target.value)}
					>
						{PROVIDER_OPTIONS.map((p) => (
							<option key={p} value={p}>
								{p || "All"}
							</option>
						))}
					</select>
				</div>
				<div>
					<div className="mb-1 text-xs text-slate-500">Workspace ID</div>
					<input
						type="number"
						className="h-9 w-32 rounded border px-2 text-sm"
						value={workspaceId}
						onChange={(e) => setWorkspaceId(e.target.value)}
						placeholder="All"
					/>
				</div>
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
							<div className="text-xs text-slate-500">Total Tokens</div>
							<div className="font-mono text-lg font-semibold">
								{data.total_tokens.toLocaleString()}
							</div>
						</div>
						<div className="rounded border p-3">
							<div className="text-xs text-slate-500">Total Cost</div>
							<div className="font-mono text-lg font-semibold">
								{formatMicros(data.total_cost_micros)}
							</div>
						</div>
						<div className="rounded border p-3">
							<div className="text-xs text-slate-500">Unreported Cost Rows</div>
							<div
								className={`font-mono text-lg font-semibold ${
									data.unreported_cost_rows > 0 ? "text-amber-600" : ""
								}`}
							>
								{data.unreported_cost_rows.toLocaleString()}
							</div>
						</div>
						<div className="rounded border p-3">
							<div className="text-xs text-slate-500">Input / Output</div>
							<div className="font-mono text-lg font-semibold">
								{data.input_tokens.toLocaleString()} / {data.output_tokens.toLocaleString()}
							</div>
						</div>
					</div>

					<div className="h-64 rounded border p-2">
						<ResponsiveContainer width="100%" height="100%">
							<LineChart data={chartData}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis dataKey="period" tick={{ fontSize: 10 }} />
								<YAxis tick={{ fontSize: 10 }} />
								<Tooltip />
								<Legend />
								<Line type="monotone" dataKey="cost_micros" name="Cost (micros)" stroke="#8884d8" />
								<Line type="monotone" dataKey="total_tokens" name="Tokens" stroke="#82ca9d" />
							</LineChart>
						</ResponsiveContainer>
					</div>

					<div className="grid grid-cols-2 gap-4">
						<div>
							<h4 className="mb-2 text-sm font-medium">By Provider</h4>
							<div className="h-48 rounded border p-2">
								<ResponsiveContainer width="100%" height="100%">
									<BarChart data={data.by_provider}>
										<CartesianGrid strokeDasharray="3 3" />
										<XAxis dataKey="key" tick={{ fontSize: 10 }} />
										<YAxis tick={{ fontSize: 10 }} />
										<Tooltip />
										<Bar dataKey="cost_micros" fill="#8884d8" />
									</BarChart>
								</ResponsiveContainer>
							</div>
						</div>
						<div>
							<h4 className="mb-2 text-sm font-medium">By Workspace</h4>
							<table className="w-full text-sm">
								<thead className="bg-slate-50 text-left dark:bg-slate-800">
									<tr>
										<th className="h-8 px-2 font-medium">Workspace</th>
										<th className="h-8 px-2 text-right font-medium">Tokens</th>
										<th className="h-8 px-2 text-right font-medium">Cost</th>
									</tr>
								</thead>
								<tbody>
									{data.by_workspace.map((w) => (
										<tr key={w.key} className="h-9 border-b">
											<td className="px-2 font-mono">{w.key}</td>
											<td className="px-2 text-right font-mono">
												{w.total_tokens.toLocaleString()}
											</td>
											<td className="px-2 text-right font-mono">{formatMicros(w.cost_micros)}</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					</div>

					<div className="grid grid-cols-2 gap-4">
						<div>
							<h4 className="mb-2 text-sm font-medium">By Model</h4>
							<table className="w-full text-sm">
								<thead className="bg-slate-50 text-left dark:bg-slate-800">
									<tr>
										<th className="h-8 px-2 font-medium">Model</th>
										<th className="h-8 px-2 text-right font-medium">Tokens</th>
										<th className="h-8 px-2 text-right font-medium">Cost</th>
									</tr>
								</thead>
								<tbody>
									{data.by_model.map((m) => (
										<tr key={m.key} className="h-9 border-b">
											<td className="px-2 font-mono">{m.key}</td>
											<td className="px-2 text-right font-mono">
												{m.total_tokens.toLocaleString()}
											</td>
											<td className="px-2 text-right font-mono">{formatMicros(m.cost_micros)}</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
						<div>
							<h4 className="mb-2 text-sm font-medium">By Usage Type</h4>
							<table className="w-full text-sm">
								<thead className="bg-slate-50 text-left dark:bg-slate-800">
									<tr>
										<th className="h-8 px-2 font-medium">Usage Type</th>
										<th className="h-8 px-2 text-right font-medium">Tokens</th>
										<th className="h-8 px-2 text-right font-medium">Cost</th>
									</tr>
								</thead>
								<tbody>
									{data.by_usage_type.map((u) => (
										<tr key={u.key} className="h-9 border-b">
											<td className="px-2 font-mono">{u.key}</td>
											<td className="px-2 text-right font-mono">
												{u.total_tokens.toLocaleString()}
											</td>
											<td className="px-2 text-right font-mono">{formatMicros(u.cost_micros)}</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					</div>
				</>
			)}
		</div>
	);
}
