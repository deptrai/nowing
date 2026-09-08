"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { AuditLogEntry } from "@/contracts/types/governance.types";
import { governanceApiService } from "@/lib/apis/governance-api.service";
import { toast } from "sonner";

interface AuditLogPanelProps {
	workspaceId: number;
	className?: string;
}

function getActionStyle(action: string) {
	if (action.includes("delete") || action.includes("remove")) {
		return "bg-rose-500/10 text-rose-500 border-rose-500/20";
	}
	if (action.includes("create") || action.includes("add")) {
		return "bg-emerald-500/10 text-emerald-500 border-emerald-500/20";
	}
	if (action.includes("update") || action.includes("archive") || action.includes("restore")) {
		return "bg-amber-500/10 text-amber-500 border-amber-500/20";
	}
	return "bg-zinc-500/10 text-zinc-400 border-zinc-500/20";
}

export function AuditLogPanel({ workspaceId, className }: AuditLogPanelProps) {
	const t = useTranslations("governance");
	const [logs, setLogs] = useState<AuditLogEntry[]>([]);
	const [isLoading, setIsLoading] = useState(false);
	const [actionPrefix, setActionPrefix] = useState("governance.");
	const [startDate, setStartDate] = useState("");
	const [endDate, setEndDate] = useState("");

	const load = useCallback(async () => {
		setIsLoading(true);
		try {
			const createdAfter = startDate ? new Date(startDate).toISOString() : undefined;
			const createdBefore = endDate ? new Date(endDate).toISOString() : undefined;
			const res = await governanceApiService.listAuditLog(workspaceId, {
				action_prefix: actionPrefix || undefined,
				created_after: createdAfter,
				created_before: createdBefore,
				page: 1,
				page_size: 50,
			});
			setLogs(res);
		} catch (error) {
			console.error("Error loading audit log:", error);
			toast.error(t("errors.load_failed"));
		} finally {
			setIsLoading(false);
		}
	}, [workspaceId, actionPrefix, startDate, endDate, t]);

	useEffect(() => {
		load();
	}, [load]);

	return (
		<section aria-label={t("audit_log.title")} className={cn("space-y-4", className)}>
			<div className="space-y-1">
				<h2 className="text-lg font-semibold">{t("audit_log.title")}</h2>
				<p className="text-sm text-muted-foreground">{t("audit_log.description")}</p>
			</div>

			<div className="grid gap-4 sm:grid-cols-4">
				<div className="space-y-2">
					<Label htmlFor="audit-action-prefix">{t("audit_log.action_filter")}</Label>
					<Input
						id="audit-action-prefix"
						value={actionPrefix}
						onChange={(e) => setActionPrefix(e.target.value)}
						placeholder="governance."
					/>
				</div>
				<div className="space-y-2">
					<Label htmlFor="audit-start">{t("audit_log.start_date")}</Label>
					<Input
						id="audit-start"
						type="date"
						value={startDate}
						onChange={(e) => setStartDate(e.target.value)}
					/>
				</div>
				<div className="space-y-2">
					<Label htmlFor="audit-end">{t("audit_log.end_date")}</Label>
					<Input
						id="audit-end"
						type="date"
						value={endDate}
						onChange={(e) => setEndDate(e.target.value)}
					/>
				</div>
				<div className="flex items-end">
					<Button onClick={load} disabled={isLoading}>
						{isLoading ? t("audit_log.loading") : t("audit_log.refresh")}
					</Button>
				</div>
			</div>

			{isLoading ? (
				<div className="space-y-2">
					<Skeleton className="h-8 w-full" />
					<Skeleton className="h-8 w-full" />
					<Skeleton className="h-8 w-full" />
				</div>
			) : logs.length === 0 ? (
				<p className="text-sm text-muted-foreground">{t("audit_log.empty")}</p>
			) : (
				<Table>
					<TableHeader>
						<TableRow>
							<TableHead>{t("audit_log.action")}</TableHead>
							<TableHead>{t("audit_log.actor")}</TableHead>
							<TableHead>{t("audit_log.timestamp")}</TableHead>
							<TableHead>{t("audit_log.diff_payload")}</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{logs.map((log) => (
							<TableRow key={log.id}>
								<TableCell>
									<Badge
										variant="outline"
										className={cn(getActionStyle(log.action), "font-mono text-xs")}
									>
										{log.action}
									</Badge>
								</TableCell>
								<TableCell className="font-mono text-xs">
									{log.actor_id || "—"}
								</TableCell>
								<TableCell>
									{new Date(log.created_at).toLocaleString(undefined, {
										dateStyle: "short",
										timeStyle: "short",
									})}
								</TableCell>
								<TableCell className="max-w-sm">
									<pre className="text-xs text-muted-foreground truncate">
										{log.diff_payload ? JSON.stringify(log.diff_payload) : "—"}
									</pre>
								</TableCell>
							</TableRow>
						))}
					</TableBody>
				</Table>
			)}
		</section>
	);
}
