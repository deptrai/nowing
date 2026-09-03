"use client";

import { Activity, AlertTriangle, CheckCircle2, Clock, MinusCircle, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { HealthStatusItem } from "@/lib/apis/admin-health-api.service";

interface HealthStatusCardProps {
	item: HealthStatusItem;
	onClick: (item: HealthStatusItem) => void;
}

export default function HealthStatusCard({ item, onClick }: HealthStatusCardProps) {
	const getStatusConfig = (status: string) => {
		switch (status) {
			case "healthy":
				return {
					badgeVariant: "default" as const,
					badgeClass: "bg-emerald-500 hover:bg-emerald-600 text-white",
					borderClass: "hover:border-emerald-500/50",
					icon: CheckCircle2,
					label: "Healthy",
				};
			case "degraded":
				return {
					badgeVariant: "secondary" as const,
					badgeClass: "bg-amber-500 hover:bg-amber-600 text-white",
					borderClass: "border-amber-500/30 hover:border-amber-500",
					icon: AlertTriangle,
					label: "Degraded",
				};
			case "unavailable":
				return {
					badgeVariant: "destructive" as const,
					badgeClass: "bg-rose-500 hover:bg-rose-600 text-white",
					borderClass: "border-rose-500/40 hover:border-rose-500",
					icon: XCircle,
					label: "Unavailable",
				};
			case "not_configured":
				return {
					badgeVariant: "outline" as const,
					badgeClass: "text-slate-500 border-slate-300",
					borderClass: "border-dashed hover:border-slate-400",
					icon: MinusCircle,
					label: "Not Configured",
				};
			default:
				return {
					badgeVariant: "outline" as const,
					badgeClass: "text-slate-400 border-slate-200",
					borderClass: "hover:border-slate-300",
					icon: MinusCircle,
					label: status.replace("_", " ").toUpperCase(),
				};
		}
	};

	const conf = getStatusConfig(item.status);
	const StatusIcon = conf.icon;

	return (
		<Card
			className={`cursor-pointer transition-all hover:shadow-sm ${conf.borderClass}`}
			onClick={() => onClick(item)}
			data-testid={`health-card-${item.service_id}`}
		>
			<CardContent className="p-4 space-y-3">
				<div className="flex items-start justify-between gap-2">
					<div className="min-w-0">
						<h3 className="font-semibold text-sm truncate" title={item.service_name}>
							{item.service_name}
						</h3>
						<p className="text-xs text-muted-foreground truncate" title={item.service_id}>
							{item.service_id}
						</p>
					</div>
					<Badge className={`text-xs shrink-0 ${conf.badgeClass}`}>
						<StatusIcon className="h-3 w-3 mr-1" />
						{conf.label}
					</Badge>
				</div>

				<div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground pt-1 border-t">
					<div className="flex items-center gap-1">
						<Activity className="h-3.5 w-3.5 text-slate-400" />
						<span>{item.latency_ms !== null ? `${item.latency_ms} ms` : "N/A"}</span>
					</div>
					<div className="text-right">
						<span>Success: {item.success_rate_15m.toFixed(0)}%</span>
					</div>
				</div>

				{item.last_error && (
					<p
						className="text-xs text-rose-500 truncate pt-1 bg-rose-50/50 dark:bg-rose-950/20 px-2 py-1 rounded"
						title={item.last_error}
					>
						Error: {item.last_error}
					</p>
				)}

				{item.suggested_action && (
					<p
						className="text-xs text-amber-600 dark:text-amber-400 truncate pt-0.5"
						title={item.suggested_action}
					>
						Action: {item.suggested_action}
					</p>
				)}

				<div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1">
					<span className="truncate">{item.display_group}</span>
					<span className="flex items-center gap-1 shrink-0">
						<Clock className="h-3 w-3" />
						{item.last_probe_at
							? new Date(item.last_probe_at).toLocaleTimeString([], {
									hour: "2-digit",
									minute: "2-digit",
									second: "2-digit",
								})
							: "Never"}
					</span>
				</div>
			</CardContent>
		</Card>
	);
}
