"use client";

import { useTranslations } from "next-intl";
import {
	Activity,
	ArrowDownLeft,
	ArrowUpRight,
	CheckCircle2,
	Clock,
	Filter,
	RefreshCw,
	XCircle,
} from "lucide-react";
import type React from "react";
import { useEffect, useState } from "react";

export interface ActivityTimelineItem {
	id: string;
	workspace_id: number;
	direction: string;
	entity_type: string;
	entity_id: string;
	status: string;
	error_message?: string | null;
	synced_at: string;
}

export interface WorkspaceActivityTimelineProps {
	workspaceId: string | number;
}

export const WorkspaceActivityTimeline: React.FC<WorkspaceActivityTimelineProps> = ({
	workspaceId,
}) => {
	const t = useTranslations("crm");
	const [items, setItems] = useState<ActivityTimelineItem[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [directionFilter, setDirectionFilter] = useState<string>("all");

	const fetchTimeline = async () => {
		setLoading(true);
		setError(null);
		try {
			const res = await fetch(`/api/v1/workspaces/${workspaceId}/crm/activity-timeline`);
			if (!res.ok) throw new Error(`Failed to load timeline: ${res.statusText}`);
			const data = await res.json();
			setItems(data.items || []);
		} catch (err: any) {
			setError(err.message || "Failed to load activity timeline");
		} finally {
			setLoading(false);
		}
	};

	useEffect(() => {
		fetchTimeline();
	}, [workspaceId]);

	const filteredItems = items.filter((item) => {
		if (directionFilter === "all") return true;
		return item.direction === directionFilter;
	});

	return (
		<div className="rounded-lg border bg-card p-6 shadow-sm">
			<div className="flex items-center justify-between pb-4 border-b">
				<div className="flex items-center gap-2">
					<Activity className="w-5 h-5 text-primary" />
					<h2 className="text-lg font-semibold">{t("crm_timeline")}</h2>
				</div>
				<div className="flex items-center gap-2">
					<select
						value={directionFilter}
						onChange={(e) => setDirectionFilter(e.target.value)}
						className="text-xs rounded-md border bg-background px-2.5 py-1.5"
					>
						<option value="all">{t("all_directions")}</option>
						<option value="inbound">{t("inbound")}</option>
						<option value="outbound">{t("outbound")}</option>
					</select>
					<button
						type="button"
						onClick={fetchTimeline}
						disabled={loading}
						className="inline-flex items-center gap-1 text-xs rounded-md border px-2.5 py-1.5 hover:bg-muted"
					>
						<RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
						{t("refresh")}
					</button>
				</div>
			</div>

			{error && (
				<div className="mt-4 p-3 rounded-md bg-destructive/10 text-destructive text-sm">
					{error}
				</div>
			)}

			{loading && items.length === 0 && (
				<div className="py-12 text-center text-sm text-muted-foreground">
					{t("loading_timeline")}
				</div>
			)}

			{!loading && filteredItems.length === 0 && (
				<div className="py-12 text-center text-sm text-muted-foreground">
					{t("no_crm_activity")}
				</div>
			)}

			<div className="mt-6 space-y-4">
				{filteredItems.map((item) => (
					<div
						key={item.id}
						className="flex items-start gap-3 p-3 rounded-md border bg-background/50 hover:bg-muted/50 transition-colors"
					>
						<div className="mt-0.5 p-1.5 rounded-full bg-muted">
							{item.direction === "inbound" ? (
								<ArrowDownLeft className="w-4 h-4 text-blue-500" />
							) : (
								<ArrowUpRight className="w-4 h-4 text-green-500" />
							)}
						</div>
						<div className="flex-1 min-w-0">
							<div className="flex items-center justify-between gap-2">
								<span className="text-sm font-medium capitalize">
									{item.direction} {item.entity_type}
								</span>
								<span className="text-xs text-muted-foreground flex items-center gap-1">
									<Clock className="w-3 h-3" />
									{new Date(item.synced_at).toLocaleString()}
								</span>
							</div>
							<p className="text-xs text-muted-foreground mt-0.5">
								{t("entity_id")}: <span className="font-mono">{item.entity_id}</span>
							</p>
							{item.error_message && (
								<p className="text-xs text-destructive mt-1 flex items-center gap-1">
									<XCircle className="w-3 h-3" />
									{item.error_message}
								</p>
							)}
						</div>
						<div>
							{item.status === "success" ? (
								<span className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-600 bg-emerald-500/10 px-2 py-0.5 rounded-full">
									<CheckCircle2 className="w-3 h-3" />
									Synced
								</span>
							) : (
								<span className="inline-flex items-center gap-1 text-[10px] font-medium text-destructive bg-destructive/10 px-2 py-0.5 rounded-full">
									<XCircle className="w-3 h-3" />
									Failed
								</span>
							)}
						</div>
					</div>
				))}
			</div>
		</div>
	);
};
