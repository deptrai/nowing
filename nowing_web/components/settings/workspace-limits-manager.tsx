"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

function formatNumber(value: number): string {
	return new Intl.NumberFormat().format(value);
}

function formatBytes(value: number): string {
	if (value <= 0) return "0 B";
	const units = ["B", "KB", "MB", "GB", "TB"];
	const i = Math.floor(Math.log10(value) / 3);
	const unit = units[Math.min(i, units.length - 1)];
	const scaled = value / 10 ** (i * 3);
	return `${scaled.toFixed(1)} ${unit}`;
}

interface LimitBarProps {
	title: string;
	used: number;
	limit: number | null;
	formatter?: (value: number) => string;
}

function LimitBar({ title, used, limit, formatter = formatNumber }: LimitBarProps) {
	const t = useTranslations("workspaceSettings");
	const unlimited = limit === null;
	const percentage = unlimited ? 0 : limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
	const nearLimit = !unlimited && percentage >= 80;

	return (
		<div className="space-y-2">
			<div className="flex items-center justify-between text-sm">
				<span className="font-medium">{title}</span>
				<span className="text-muted-foreground">
					{unlimited
						? `${formatter(used)} / ${t("limits_unlimited")}`
						: `${formatter(used)} / ${formatter(limit)}`}
				</span>
			</div>
			{!unlimited && <Progress value={percentage} />}
			{nearLimit && (
				<p className="text-xs text-amber-600 dark:text-amber-400">{t("limits_near_limit")}</p>
			)}
		</div>
	);
}

interface WorkspaceLimitsManagerProps {
	workspaceId: string;
}

export function WorkspaceLimitsManager({ workspaceId }: WorkspaceLimitsManagerProps) {
	const t = useTranslations("workspaceSettings");
	const numericId = Number(workspaceId);

	const { data, isLoading } = useQuery({
		queryKey: cacheKeys.workspaces.limits(numericId),
		queryFn: () => workspacesApiService.getWorkspaceLimits(numericId),
		enabled: Number.isFinite(numericId) && numericId > 0,
	});

	const upgradeUrl = process.env.NEXT_PUBLIC_UPGRADE_URL;

	const limits = [
		{
			key: "documents",
			title: t("limits_documents"),
			used: data?.usage.documents ?? 0,
			limit: data?.max_documents ?? null,
		},
		{
			key: "members",
			title: t("limits_members"),
			used: data?.usage.members ?? 0,
			limit: data?.max_members ?? null,
		},
		{
			key: "runs",
			title: t("limits_runs"),
			used: data?.usage.runs ?? 0,
			limit: data?.max_runs ?? null,
		},
		{
			key: "storage",
			title: t("limits_storage"),
			used: data?.usage.storage_bytes ?? 0,
			limit: data?.max_storage_bytes ?? null,
			formatter: formatBytes,
		},
	];

	const showUpgradeCta =
		!!upgradeUrl &&
		limits.some(
			(item) => item.limit !== null && item.limit > 0 && (item.used / item.limit) * 100 >= 80
		);

	if (!Number.isFinite(numericId) || numericId <= 0) {
		return (
			<div className="flex min-h-[20rem] items-center justify-center">
				<p className="text-muted-foreground">{t("limits_invalid_workspace")}</p>
			</div>
		);
	}

	return (
		<div className="space-y-6">
			<div>
				<h1 className="font-serif text-2xl sm:text-3xl font-normal tracking-tight text-foreground">
					{t("limits_title")}
				</h1>
				<p className="text-xs sm:text-sm text-muted-foreground font-sans">
					{t("limits_description")}
				</p>
			</div>

			<Card>
				<CardHeader className="flex flex-row items-center justify-between pb-2">
					<CardTitle className="text-base font-medium">{t("limits_plan_label")}</CardTitle>
					{isLoading ? (
						<Skeleton className="h-6 w-20" aria-hidden="true" />
					) : (
						<Badge variant="secondary">{data?.plan_tier ?? t("limits_plan_unknown")}</Badge>
					)}
				</CardHeader>
				<CardContent className="space-y-6">
					{isLoading
						? ["documents", "members", "runs", "storage"].map((key) => (
								<div key={key} className="space-y-2">
									<Skeleton className="h-4 w-32" aria-hidden="true" />
									<Skeleton className="h-4 w-full" />
								</div>
							))
						: limits.map((item) => (
								<LimitBar
									key={item.key}
									title={item.title}
									used={item.used}
									limit={item.limit}
									formatter={item.formatter}
								/>
							))}

					{showUpgradeCta && (
						<Button asChild variant="default" className="w-full sm:w-auto">
							<a href={upgradeUrl} target="_blank" rel="noopener noreferrer">
								{t("limits_upgrade_cta")}
								<ExternalLink className="ml-2 h-4 w-4" aria-hidden="true" />
							</a>
						</Button>
					)}
				</CardContent>
			</Card>
		</div>
	);
}
