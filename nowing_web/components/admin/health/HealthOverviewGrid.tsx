"use client";

import { AlertTriangle, CheckCircle2, MinusCircle, ShieldAlert, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { HealthOverviewResponse } from "@/lib/apis/admin-health-api.service";

interface HealthOverviewGridProps {
	overview: HealthOverviewResponse | null;
}

export default function HealthOverviewGrid({ overview }: HealthOverviewGridProps) {
	if (!overview) {
		return null;
	}

	const counts = overview.status_counts || {
		healthy: 0,
		degraded: 0,
		unavailable: 0,
		not_configured: 0,
		disabled: 0,
	};

	return (
		<div className="grid grid-cols-2 md:grid-cols-5 gap-4" data-testid="health-overview-grid">
			<Card className="border-green-200 dark:border-green-900 bg-green-50/20 dark:bg-green-950/10">
				<CardHeader className="pb-2">
					<CardTitle className="text-xs font-medium text-green-700 dark:text-green-400 flex items-center justify-between">
						<span>Healthy</span>
						<CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="text-2xl font-bold text-green-700 dark:text-green-300">
						{counts.healthy}
					</div>
					<p className="text-xs text-muted-foreground mt-1">Normal operation</p>
				</CardContent>
			</Card>

			<Card className="border-amber-200 dark:border-amber-900 bg-amber-50/20 dark:bg-amber-950/10">
				<CardHeader className="pb-2">
					<CardTitle className="text-xs font-medium text-amber-700 dark:text-amber-400 flex items-center justify-between">
						<span>Degraded</span>
						<AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="text-2xl font-bold text-amber-700 dark:text-amber-300">
						{counts.degraded}
					</div>
					<p className="text-xs text-muted-foreground mt-1">High latency / errors</p>
				</CardContent>
			</Card>

			<Card className="border-red-200 dark:border-red-900 bg-red-50/20 dark:bg-red-950/10">
				<CardHeader className="pb-2">
					<CardTitle className="text-xs font-medium text-red-700 dark:text-red-400 flex items-center justify-between">
						<span>Unavailable</span>
						<XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="text-2xl font-bold text-red-700 dark:text-red-300">
						{counts.unavailable}
					</div>
					<p className="text-xs text-muted-foreground mt-1">Service unreachable</p>
				</CardContent>
			</Card>

			<Card className="border-slate-200 dark:border-slate-800">
				<CardHeader className="pb-2">
					<CardTitle className="text-xs font-medium text-slate-600 dark:text-slate-400 flex items-center justify-between">
						<span>Not Configured</span>
						<MinusCircle className="h-4 w-4 text-slate-500" />
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="text-2xl font-bold text-slate-700 dark:text-slate-300">
						{counts.not_configured}
					</div>
					<p className="text-xs text-muted-foreground mt-1">Missing credentials</p>
				</CardContent>
			</Card>

			<Card className="border-slate-200 dark:border-slate-800">
				<CardHeader className="pb-2">
					<CardTitle className="text-xs font-medium text-slate-600 dark:text-slate-400 flex items-center justify-between">
						<span>Disabled</span>
						<ShieldAlert className="h-4 w-4 text-slate-500" />
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="text-2xl font-bold text-slate-700 dark:text-slate-300">
						{counts.disabled}
					</div>
					<p className="text-xs text-muted-foreground mt-1">Turned off by config</p>
				</CardContent>
			</Card>
		</div>
	);
}
