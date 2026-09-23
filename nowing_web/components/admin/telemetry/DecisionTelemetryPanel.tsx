"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
	Bar,
	BarChart,
	CartesianGrid,
	Legend,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";
import {
	adminTelemetryApiService,
	type DecisionTelemetry,
} from "@/lib/apis/admin-telemetry-api.service";

const WINDOW_OPTIONS = [
	{ label: "1h", value: 1 },
	{ label: "6h", value: 6 },
	{ label: "24h", value: 24 },
	{ label: "7d", value: 168 },
	{ label: "30d", value: 720 },
] as const;

const STACK_COLORS = ["#8884d8", "#82ca9d", "#ffc658", "#ff8042", "#0088fe", "#00c49f", "#d084d0"];

function formatMicros(micros: number): string {
	return `$${(micros / 1_000_000).toFixed(4)}`;
}

function formatUsd(usd: number): string {
	return `$${usd.toFixed(2)}`;
}

interface DecisionTelemetryPanelProps {
	tick?: number;
}

export default function DecisionTelemetryPanel({ tick }: DecisionTelemetryPanelProps) {
	const t = useTranslations("admin");
	const [windowHours, setWindowHours] = useState<number>(24);
	const [workspaceId, setWorkspaceId] = useState<string>("");
	const [data, setData] = useState<DecisionTelemetry | null>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const load = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const parsed = workspaceId ? parseInt(workspaceId, 10) : NaN;
			const workspace_id = Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
			const d = await adminTelemetryApiService.decisionTelemetry({
				window_hours: windowHours as 1 | 6 | 24 | 168 | 720,
				workspace_id,
			});
			setData(d);
		} catch (err) {
			setError(err instanceof Error ? err.message : t("telemetry.decision_failed_load"));
		} finally {
			setLoading(false);
		}
	}, [windowHours, workspaceId, t]);

	// biome-ignore lint/correctness/useExhaustiveDependencies: tick is the auto-refresh trigger
	useEffect(() => {
		void load();
	}, [load, tick]);

	// Pivot daily[] (period x task) into stacked-bar rows keyed by period.
	const { chartData, tasks } = useMemo(() => {
		const taskSet = new Set<string>();
		const byPeriod = new Map<string, Record<string, number | string>>();
		for (const bucket of data?.daily ?? []) {
			taskSet.add(bucket.task);
			const row = byPeriod.get(bucket.period) ?? { period: bucket.period };
			row[bucket.task] = bucket.calls;
			byPeriod.set(bucket.period, row);
		}
		return {
			chartData: Array.from(byPeriod.values()),
			tasks: Array.from(taskSet).sort(),
		};
	}, [data]);

	return (
		<div className="space-y-4 rounded border p-4">
			<div className="flex flex-wrap items-end gap-3">
				<div>
					<h3 className="text-sm font-medium">{t("telemetry.decision_title")}</h3>
					<p className="text-xs text-slate-500">{t("telemetry.decision_desc")}</p>
				</div>
				<div className="ml-auto flex items-end gap-3">
					<div>
						<div className="mb-1 text-xs text-slate-500">{t("telemetry.decision_window")}</div>
						<select
							className="h-9 rounded border px-2 text-sm"
							value={windowHours}
							onChange={(e) => setWindowHours(parseInt(e.target.value, 10))}
							aria-label={t("telemetry.decision_window")}
						>
							{WINDOW_OPTIONS.map((w) => (
								<option key={w.value} value={w.value}>
									{w.label}
								</option>
							))}
						</select>
					</div>
					<div>
						<div className="mb-1 text-xs text-slate-500">
							{t("telemetry.decision_workspace_id")}
						</div>
						<input
							type="number"
							className="h-9 w-32 rounded border px-2 text-sm"
							value={workspaceId}
							onChange={(e) => setWorkspaceId(e.target.value)}
							placeholder={t("telemetry.decision_all")}
							aria-label={t("telemetry.decision_workspace_id")}
						/>
					</div>
					<button
						type="button"
						onClick={load}
						className="h-9 rounded border bg-slate-100 px-3 text-sm hover:bg-slate-200"
					>
						{t("telemetry.decision_refresh")}
					</button>
				</div>
			</div>

			{data?.cost_alert.exceeded && (
				<div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
					{t("telemetry.decision_cost_alert", {
						cost: formatMicros(data.cost_alert.today_cost_micros),
						threshold: formatUsd(data.cost_alert.threshold_usd),
					})}
				</div>
			)}

			{loading && <div className="text-sm text-slate-500">{t("telemetry.decision_loading")}</div>}
			{error && (
				<div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
					{error}
				</div>
			)}

			{data && (
				<>
					{data.daily.length === 0 && data.by_task.length === 0 && data.models.length === 0 && (
						<div className="rounded border border-dashed px-3 py-6 text-center text-sm text-slate-500">
							{t("telemetry.decision_empty")}
						</div>
					)}
					<div className="grid grid-cols-4 gap-4">
						<div className="rounded border p-3">
							<div className="text-xs text-slate-500">{t("telemetry.decision_calls")}</div>
							<div className="font-mono text-lg font-semibold">
								{data.total_calls.toLocaleString()}
							</div>
						</div>
						<div className="rounded border p-3">
							<div className="text-xs text-slate-500">{t("telemetry.decision_cost")}</div>
							<div className="font-mono text-lg font-semibold">
								{formatMicros(data.total_cost_micros)}
							</div>
						</div>
						<div className="rounded border p-3">
							<div className="text-xs text-slate-500">{t("telemetry.decision_median")}</div>
							<div className="font-mono text-lg font-semibold">
								{data.median_latency_ms !== null
									? `${Math.round(data.median_latency_ms)} ms`
									: t("telemetry.decision_na")}
							</div>
						</div>
						<div className="rounded border p-3">
							<div className="text-xs text-slate-500">{t("telemetry.decision_accuracy")}</div>
							<div className="font-mono text-lg font-semibold">
								{data.accuracy !== null
									? `${(data.accuracy * 100).toFixed(1)}%`
									: t("telemetry.decision_na")}
							</div>
							<div className="text-xs text-slate-400">
								{t("telemetry.decision_accuracy_labeled", { count: data.labeled })}
							</div>
						</div>
					</div>

					<div className="h-64 rounded border p-2">
						<h4 className="mb-1 text-sm font-medium">{t("telemetry.decision_chart_title")}</h4>
						<ResponsiveContainer width="100%" height="90%">
							<BarChart data={chartData}>
								<CartesianGrid strokeDasharray="3 3" />
								<XAxis dataKey="period" tick={{ fontSize: 10 }} />
								<YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
								<Tooltip />
								<Legend />
								{tasks.map((task, i) => (
									<Bar
										key={task}
										// Function accessor, not a string path — a task name
										// containing a dot would be parsed as a nested key.
										dataKey={(row: Record<string, unknown>) => row[task]}
										name={task}
										stackId="calls"
										fill={STACK_COLORS[i % STACK_COLORS.length]}
									/>
								))}
							</BarChart>
						</ResponsiveContainer>
					</div>

					<div className="grid grid-cols-2 gap-4">
						<div>
							<h4 className="mb-2 text-sm font-medium">{t("telemetry.decision_by_task")}</h4>
							<table className="w-full text-sm">
								<thead className="bg-slate-50 text-left dark:bg-slate-800">
									<tr>
										<th className="h-8 px-2 font-medium">{t("telemetry.decision_task")}</th>
										<th className="h-8 px-2 text-right font-medium">
											{t("telemetry.decision_calls")}
										</th>
										<th className="h-8 px-2 text-right font-medium">
											{t("telemetry.decision_median")}
										</th>
										<th className="h-8 px-2 text-right font-medium">
											{t("telemetry.decision_cost")}
										</th>
									</tr>
								</thead>
								<tbody>
									{data.by_task.map((row) => (
										<tr key={row.task} className="h-9 border-b">
											<td className="px-2 font-mono">{row.task}</td>
											<td className="px-2 text-right font-mono">{row.calls.toLocaleString()}</td>
											<td className="px-2 text-right font-mono">
												{row.median_latency_ms !== null
													? `${Math.round(row.median_latency_ms)}`
													: t("telemetry.decision_na")}
											</td>
											<td className="px-2 text-right font-mono">{formatMicros(row.cost_micros)}</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
						<div>
							<h4 className="mb-2 text-sm font-medium">
								{t("telemetry.decision_models")}
								{data.drift_detected && (
									<span className="ml-2 rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
										{t("telemetry.decision_drift")}
									</span>
								)}
							</h4>
							<div className="mb-1 text-xs text-slate-500">
								{t("telemetry.decision_pinned", { model: data.pinned_model })}
							</div>
							<table className="w-full text-sm">
								<thead className="bg-slate-50 text-left dark:bg-slate-800">
									<tr>
										<th className="h-8 px-2 font-medium">{t("telemetry.decision_model")}</th>
										<th className="h-8 px-2 font-medium">{t("telemetry.decision_backend")}</th>
										<th className="h-8 px-2 text-right font-medium">
											{t("telemetry.decision_calls")}
										</th>
										<th className="h-8 px-2 font-medium">{t("telemetry.decision_last_seen")}</th>
									</tr>
								</thead>
								<tbody>
									{data.models.map((m) => (
										<tr key={`${m.backend}:${m.model}`} className="h-9 border-b">
											<td className="px-2 font-mono">
												{m.model}
												{m.model !== data.pinned_model && m.backend === "jev" && (
													<span className="ml-1 text-amber-600">*</span>
												)}
											</td>
											<td className="px-2 font-mono">{m.backend}</td>
											<td className="px-2 text-right font-mono">{m.calls.toLocaleString()}</td>
											<td className="px-2 font-mono text-xs">
												{m.last_seen
													? new Date(m.last_seen).toLocaleString()
													: t("telemetry.decision_na")}
											</td>
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
