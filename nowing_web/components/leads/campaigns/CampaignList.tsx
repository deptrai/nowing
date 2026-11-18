"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { CampaignStatus } from "@/contracts/types/campaign.types";
import { leadsApiService } from "@/lib/apis/leads-api.service";
import { AppError } from "@/lib/error";

const PAGE_SIZE = 20;

// Badge variant theo status — archived xám muted; 7 giá trị khớp backend
// CampaignStatus enum + campaignStatusSchema.
const STATUS_BADGE: Record<
	CampaignStatus,
	{ variant: "default" | "secondary" | "destructive" | "outline"; className?: string }
> = {
	draft: { variant: "outline" },
	scheduled: { variant: "secondary" },
	running: { variant: "default" },
	paused: { variant: "secondary" },
	completed: { variant: "default" },
	failed: { variant: "destructive" },
	archived: { variant: "secondary", className: "text-muted-foreground" },
};

const fmtDateTime = (iso?: string | null) => (iso ? new Date(iso).toLocaleString("vi-VN") : "-");

const SKELETON_KEYS = ["s1", "s2", "s3", "s4", "s5"];

export function CampaignList({ workspaceId }: { workspaceId: string }) {
	const t = useTranslations("leads");
	const [page, setPage] = useState(1);
	const [includeImplicit, setIncludeImplicit] = useState(false);

	const { data, isPending, isError, error, refetch } = useQuery({
		queryKey: ["leads-campaigns", workspaceId, page, includeImplicit],
		queryFn: () =>
			leadsApiService.listCampaigns(workspaceId, {
				page,
				page_size: PAGE_SIZE,
				include_implicit: includeImplicit,
			}),
	});

	const campaigns = data?.items ?? [];
	const total = data?.total ?? 0;
	const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

	const toggleImplicit = (checked: boolean) => {
		setIncludeImplicit(checked);
		setPage(1);
	};

	return (
		<div className="flex flex-col gap-4">
			<div className="flex items-center justify-between">
				<h1 className="text-xl font-semibold">{t("campaigns_title")}</h1>
				<div className="flex items-center gap-4">
					<div className="flex items-center gap-2">
						<Switch
							id="campaigns-show-auto"
							checked={includeImplicit}
							onCheckedChange={toggleImplicit}
						/>
						<Label htmlFor="campaigns-show-auto" className="text-sm text-muted-foreground">
							{t("campaigns_show_auto")}
						</Label>
					</div>
					<Button asChild size="sm">
						<Link href={`/dashboard/${workspaceId}/leads/campaigns/new`}>
							<Plus className="mr-1 h-4 w-4" />
							{t("campaigns_new")}
						</Link>
					</Button>
				</div>
			</div>

			{isError ? (
				<div className="flex flex-col items-center gap-3 rounded-md border border-dashed py-16">
					<p className="text-sm text-destructive">
						{error instanceof AppError && error.status === 403
							? t("campaigns_error_forbidden")
							: t("campaigns_error_load")}
					</p>
					<Button variant="outline" size="sm" onClick={() => refetch()}>
						{t("campaigns_retry")}
					</Button>
				</div>
			) : isPending ? (
				<div className="space-y-2">
					{SKELETON_KEYS.map((k) => (
						<Skeleton key={k} className="h-10 w-full" />
					))}
				</div>
			) : campaigns.length === 0 ? (
				<div className="flex flex-col items-center gap-3 rounded-md border border-dashed py-16">
					<p className="text-sm font-medium">{t("campaigns_empty_title")}</p>
					<p className="text-sm text-muted-foreground">{t("campaigns_empty_hint")}</p>
					<Button asChild size="sm">
						<Link href={`/dashboard/${workspaceId}/leads/campaigns/new`}>
							{t("campaigns_empty_cta")}
						</Link>
					</Button>
				</div>
			) : (
				<>
					<Table>
						<TableHeader>
							<TableRow>
								<TableHead>{t("campaigns_col_name")}</TableHead>
								<TableHead>{t("campaigns_col_status")}</TableHead>
								<TableHead>{t("campaigns_col_direction")}</TableHead>
								<TableHead className="text-right">{t("campaigns_col_leads")}</TableHead>
								<TableHead>{t("campaigns_col_last_run")}</TableHead>
								<TableHead>{t("campaigns_col_created")}</TableHead>
							</TableRow>
						</TableHeader>
						<TableBody>
							{campaigns.map((c) => {
								const badge = STATUS_BADGE[c.status] ?? STATUS_BADGE.draft;
								return (
									<TableRow key={c.id}>
										<TableCell>
											<Link
												href={`/dashboard/${workspaceId}/leads/campaigns/${c.id}`}
												className="font-medium hover:underline"
											>
												{c.name}
											</Link>
											{c.source && c.source !== "created" ? (
												<Badge variant="outline" className="ml-2 text-muted-foreground">
													{t("campaigns_auto_badge")}
												</Badge>
											) : null}
										</TableCell>
										<TableCell>
											<Badge variant={badge.variant} className={badge.className}>
												{t(`campaigns_status_${c.status}`)}
											</Badge>
										</TableCell>
										<TableCell>
											{c.direction === "supply"
												? t("campaigns_dir_supply")
												: t("campaigns_dir_demand")}
										</TableCell>
										<TableCell className="text-right">{c.collected_leads_count}</TableCell>
										<TableCell>{fmtDateTime(c.last_run_at)}</TableCell>
										<TableCell>{fmtDateTime(c.created_at)}</TableCell>
									</TableRow>
								);
							})}
						</TableBody>
					</Table>

					<div className="flex items-center justify-between">
						<span className="text-sm text-muted-foreground">
							{t("campaigns_page_of", { page, total: totalPages })}
						</span>
						<div className="flex gap-2">
							<Button
								variant="outline"
								size="sm"
								disabled={page <= 1}
								onClick={() => setPage((p) => Math.max(1, p - 1))}
							>
								<ChevronLeft className="mr-1 h-4 w-4" />
								{t("campaigns_prev")}
							</Button>
							<Button
								variant="outline"
								size="sm"
								disabled={page >= totalPages}
								onClick={() => setPage((p) => p + 1)}
							>
								{t("campaigns_next")}
								<ChevronRight className="ml-1 h-4 w-4" />
							</Button>
						</div>
					</div>
				</>
			)}
		</div>
	);
}
