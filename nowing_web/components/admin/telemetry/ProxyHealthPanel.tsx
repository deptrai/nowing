"use client";

import { useCallback, useEffect, useState } from "react";
import {
	adminTelemetryApiService,
	type ProxyHealthResponse,
} from "@/lib/apis/admin-telemetry-api.service";

function statusBadgeClass(status: string) {
	switch (status) {
		case "healthy":
			return "bg-green-100 text-green-700";
		case "degraded":
			return "bg-amber-100 text-amber-700";
		case "dead":
			return "bg-red-100 text-red-700";
		default:
			return "bg-slate-100 text-slate-600";
	}
}

interface ProxyHealthPanelProps {
	tick?: number;
}

export default function ProxyHealthPanel({ tick }: ProxyHealthPanelProps) {
	const [data, setData] = useState<ProxyHealthResponse | null>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const load = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const d = await adminTelemetryApiService.proxyHealth();
			setData(d);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to load proxy health");
		} finally {
			setLoading(false);
		}
	}, []);

	// biome-ignore lint/correctness/useExhaustiveDependencies: tick is the auto-refresh trigger
	useEffect(() => {
		void load();
	}, [load, tick]);

	return (
		<div className="space-y-4 rounded border p-4">
			<div className="flex items-center justify-between">
				<h3 className="text-lg font-semibold">Proxy Health</h3>
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
							<div className="text-xs text-slate-500">Status</div>
							<div
								className={`inline-flex rounded px-2 py-0.5 text-sm font-medium ${statusBadgeClass(data.status)}`}
							>
								{data.status}
							</div>
						</div>
						<div className="rounded border p-3">
							<div className="text-xs text-slate-500">Provider</div>
							<div className="font-mono text-sm">{data.provider}</div>
						</div>
						<div className="rounded border p-3">
							<div className="text-xs text-slate-500">Healthy / Degraded / Dead</div>
							<div className="font-mono text-sm">
								{data.healthy} / {data.degraded} / {data.dead}
							</div>
						</div>
						<div className="rounded border p-3">
							<div className="text-xs text-slate-500">Total</div>
							<div className="font-mono text-sm">{data.total}</div>
						</div>
					</div>

					<table className="w-full text-sm">
						<thead className="bg-slate-50 text-left dark:bg-slate-800">
							<tr>
								<th className="h-9 px-2 font-medium">Provider</th>
								<th className="h-9 px-2 font-medium">Status</th>
								<th className="h-9 px-2 text-right font-medium">Latency (ms)</th>
								<th className="h-9 px-2 text-right font-medium">Success %</th>
								<th className="h-9 px-2 font-medium">Last Error</th>
							</tr>
						</thead>
						<tbody>
							{data.snapshots.map((s) => (
								<tr key={s.provider} className="h-9 border-b">
									<td className="px-2 font-mono text-xs">{s.provider}</td>
									<td className="px-2">
										<span
											className={`rounded px-1.5 py-0.5 text-xs font-medium ${statusBadgeClass(s.status)}`}
										>
											{s.status}
										</span>
									</td>
									<td className="px-2 text-right font-mono">
										{s.latency_ms?.toLocaleString() ?? "-"}
									</td>
									<td className="px-2 text-right font-mono">
										{(s.success_rate * 100).toFixed(0)}%
									</td>
									<td
										className="px-2 max-w-xs truncate text-xs text-red-600"
										title={s.last_error ?? ""}
									>
										{s.last_error ?? "-"}
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</>
			)}
		</div>
	);
}
