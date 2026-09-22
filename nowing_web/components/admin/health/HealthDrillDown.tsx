"use client";

import { Activity, AlertCircle, CheckCircle2, Clock, Play, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import {
	adminHealthApiService,
	type HealthHistoryItem,
	type HealthProbeResultResponse,
	type HealthStatusItem,
} from "@/lib/apis/admin-health-api.service";

interface HealthDrillDownProps {
	item: HealthStatusItem | null;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onProbeSuccess?: (result: HealthProbeResultResponse) => void;
}

export default function HealthDrillDown({
	item,
	open,
	onOpenChange,
	onProbeSuccess,
}: HealthDrillDownProps) {
	const t = useTranslations("admin");
	const [history, setHistory] = useState<HealthHistoryItem[]>([]);
	const [loadingHistory, setLoadingHistory] = useState(false);
	const [probing, setProbing] = useState(false);
	const [probeResult, setProbeResult] = useState<HealthProbeResultResponse | null>(null);

	useEffect(() => {
		if (item && open) {
			setLoadingHistory(true);
			setProbeResult(null);
			adminHealthApiService
				.getHistory(item.service_id, 24)
				.then((res) => {
					setHistory(res.items || []);
				})
				.catch((err) => {
					console.error("Failed to load health history:", err);
				})
				.finally(() => {
					setLoadingHistory(false);
				});
		}
	}, [item, open]);

	if (!item) return null;

	const handleRunProbe = async () => {
		setProbing(true);
		try {
			const res = await adminHealthApiService.runProbe(item.service_id);
			setProbeResult(res);
			if (onProbeSuccess) {
				onProbeSuccess(res);
			}
			// Refresh history
			const histRes = await adminHealthApiService.getHistory(item.service_id, 24);
			setHistory(histRes.items || []);
		} catch (err) {
			console.error("Failed to run probe:", err);
		} finally {
			setProbing(false);
		}
	};

	const chartData = history.map((h) => ({
		time: new Date(h.probe_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
		latency: h.latency_ms ?? 0,
		status: h.status,
	}));

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent
				className="max-w-2xl max-h-[85vh] overflow-y-auto"
				data-testid="health-drilldown-modal"
			>
				<DialogHeader>
					<div className="flex items-center justify-between gap-4 mr-6">
						<div>
							<DialogTitle className="text-xl font-bold flex items-center gap-2">
								<span>{item.service_name}</span>
								<Badge variant="outline" className="text-xs">
									{item.category}
								</Badge>
							</DialogTitle>
							<DialogDescription className="text-xs text-muted-foreground mt-1">
								{item.service_id} • {t("group")}: {item.display_group}
							</DialogDescription>
						</div>
						<Badge
							className={`text-xs ${
								item.status === "healthy"
									? "bg-emerald-500 text-white"
									: item.status === "degraded"
										? "bg-amber-500 text-white"
										: item.status === "unavailable"
											? "bg-rose-500 text-white"
											: "bg-slate-400 text-white"
							}`}
						>
							{item.status.toUpperCase()}
						</Badge>
					</div>
				</DialogHeader>

				<div className="space-y-5 my-2">
					{/* Status details bar */}
					<div className="grid grid-cols-3 gap-3 p-3 bg-muted/40 rounded-lg text-xs">
						<div>
							<span className="text-muted-foreground block mb-1">{t("latency")}</span>
							<span className="font-semibold text-sm">
								{item.latency_ms !== null ? `${item.latency_ms} ms` : "N/A"}
							</span>
						</div>
						<div>
							<span className="text-muted-foreground block mb-1">{t("success_15m")}</span>
							<span className="font-semibold text-sm">{item.success_rate_15m.toFixed(1)}%</span>
						</div>
						<div>
							<span className="text-muted-foreground block mb-1">{t("last_probe")}</span>
							<span className="font-semibold text-sm">
								{item.last_probe_at
									? new Date(item.last_probe_at).toLocaleTimeString()
									: t("never")}
							</span>
						</div>
					</div>

					{/* Suggested Action */}
					{item.suggested_action && (
						<div className="p-3 bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/50 rounded-lg text-xs space-y-1">
							<span className="font-semibold text-amber-800 dark:text-amber-300">
								{t("suggested_action")}
							</span>
							<p className="text-amber-900 dark:text-amber-200">{item.suggested_action}</p>
						</div>
					)}

					{/* Last error block */}
					{item.last_error && (
						<div className="p-3 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900 rounded-lg text-xs space-y-1">
							<div className="flex items-center gap-1 font-semibold text-rose-600 dark:text-rose-400">
								<AlertCircle className="h-4 w-4" />
								<span>{t("last_error")}</span>
							</div>
							<p className="font-mono text-[11px] text-rose-800 dark:text-rose-300 break-words">
								{item.last_error}
							</p>
						</div>
					)}

					{/* 24-Hour Latency Chart */}
					{chartData.length > 0 && (
						<div className="space-y-1.5">
							<h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
								{t("trend_24h")}
							</h4>
							<div className="h-32 w-full pt-2">
								<ResponsiveContainer width="100%" height="100%">
									<AreaChart data={chartData}>
										<XAxis dataKey="time" tick={{ fontSize: 10 }} />
										<YAxis tick={{ fontSize: 10 }} width={35} />
										<Tooltip
											contentStyle={{ fontSize: "11px", borderRadius: "6px" }}
											formatter={(val: unknown) => [
												`${typeof val === "number" ? val : 0} ms`,
												t("latency"),
											]}
										/>
										<Area
											type="monotone"
											dataKey="latency"
											stroke="#10b981"
											fill="#10b981"
											fillOpacity={0.2}
										/>
									</AreaChart>
								</ResponsiveContainer>
							</div>
						</div>
					)}

					{/* Metadata payload */}
					{item.metadata_payload && Object.keys(item.metadata_payload).length > 0 && (
						<div className="space-y-1.5">
							<h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
								{t("metadata_config")}
							</h4>
							<pre className="p-3 bg-muted/60 rounded-md text-[11px] font-mono overflow-x-auto max-h-36">
								{JSON.stringify(item.metadata_payload, null, 2)}
							</pre>
						</div>
					)}

					{/* On-demand probe output */}
					{probeResult && (
						<div className="p-3 border rounded-lg bg-slate-50 dark:bg-slate-900 text-xs space-y-2">
							<div className="flex items-center justify-between">
								<span className="font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
									<CheckCircle2 className="h-4 w-4" /> {t("test_probe_completed")}
								</span>
								<span className="text-[11px] text-muted-foreground">
									{probeResult.latency_ms} ms
								</span>
							</div>
							<div className="text-[11px]">
								{t("status")} <Badge variant="outline">{probeResult.status}</Badge>
							</div>
							{probeResult.last_error && (
								<p className="text-rose-500 font-mono text-[11px]">{probeResult.last_error}</p>
							)}
						</div>
					)}

					{/* 24-hour probe history list */}
					<div className="space-y-2">
						<div className="flex items-center justify-between">
							<h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
								<Activity className="h-3.5 w-3.5" />{" "}
								{t("probe_history_24h", { count: history.length })}
							</h4>
						</div>

						{loadingHistory ? (
							<div className="py-6 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
								<RefreshCw className="h-4 w-4 animate-spin" /> {t("loading_history")}
							</div>
						) : history.length === 0 ? (
							<div className="py-6 text-center text-xs text-muted-foreground border border-dashed rounded-lg">
								{t("no_history_records")}
							</div>
						) : (
							<div className="border rounded-md divide-y max-h-48 overflow-y-auto">
								{history.map((h) => (
									<div key={h.id} className="p-2.5 text-xs flex items-center justify-between gap-2">
										<div className="flex items-center gap-2">
											<span
												className={`h-2 w-2 rounded-full ${
													h.status === "healthy"
														? "bg-emerald-500"
														: h.status === "degraded"
															? "bg-amber-500"
															: "bg-rose-500"
												}`}
											/>
											<span className="font-medium capitalize">{h.status}</span>
											{h.error_message && (
												<span
													className="text-[11px] text-rose-500 truncate max-w-xs"
													title={h.error_message}
												>
													{h.error_message}
												</span>
											)}
										</div>
										<div className="flex items-center gap-3 text-[11px] text-muted-foreground shrink-0">
											<span>{h.latency_ms !== null ? `${h.latency_ms}ms` : "-"}</span>
											<span className="flex items-center gap-1">
												<Clock className="h-3 w-3" />
												{new Date(h.probe_at).toLocaleTimeString([], {
													hour: "2-digit",
													minute: "2-digit",
													second: "2-digit",
												})}
											</span>
										</div>
									</div>
								))}
							</div>
						)}
					</div>
				</div>

				<DialogFooter className="flex items-center justify-between sm:justify-between border-t pt-3">
					<Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
						{t("close")}
					</Button>

					<Button
						size="sm"
						onClick={handleRunProbe}
						disabled={probing}
						className="gap-1.5"
						data-testid="btn-run-probe"
					>
						{probing ? (
							<RefreshCw className="h-3.5 w-3.5 animate-spin" />
						) : (
							<Play className="h-3.5 w-3.5" />
						)}
						{probing ? t("probing") : t("test_now")}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
