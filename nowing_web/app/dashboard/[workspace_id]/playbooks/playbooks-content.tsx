"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import {
	BadgeCheck,
	BookOpen,
	Building2,
	Coins,
	Flame,
	Play,
	Search,
	ShoppingBag,
	Sparkles,
	TrendingUp,
	Users,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { playbooksListAtom } from "@/atoms/playbooks/playbooks-query.atoms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import type { PlaybookSummary } from "@/contracts/types/playbook.types";
import type { Workspace } from "@/contracts/types/workspace.types";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { PlaybookInstantiateDialog } from "./playbook-instantiate-dialog";

interface PlaybooksContentProps {
	workspaceId: number;
}

const CATEGORIES_CONFIG = [
	{ id: "all", labelKey: "cat_all", icon: Sparkles },
	{ id: "realestate", labelKey: "cat_realestate", icon: Building2 },
	{ id: "recruitment", labelKey: "cat_recruitment", icon: Users },
	{ id: "b2b", labelKey: "cat_b2b", icon: TrendingUp },
	{ id: "ecommerce", labelKey: "cat_ecommerce", icon: ShoppingBag },
] as const;

const DEFAULT_CREDIT_COST = 25;

function mapWorkspaceVerticalToCategory(vertical: Workspace["vertical"] | undefined): string {
	switch (vertical) {
		case "real_estate":
			return "realestate";
		case "b2b_equipment":
			return "b2b";
		default:
			return "all";
	}
}

function formatCompactNumber(value: number): string {
	if (value >= 1_000_000) {
		const m = value / 1_000_000;
		return `${m % 1 === 0 ? Math.trunc(m) : m.toFixed(1)}m`;
	}
	if (value >= 1000) {
		const k = value / 1000;
		return `${k % 1 === 0 ? Math.trunc(k) : k.toFixed(1)}k`;
	}
	return String(value);
}

function formatRunCount(
	count: number | null | undefined,
	t: (key: any, options?: any) => string
): string {
	const safeCount = count ?? 0;
	if (safeCount === 0) {
		return t("run_count_zero");
	}
	if (safeCount < 1000) {
		return t("run_count_under_1k", { count: safeCount });
	}
	return t("run_count_over_1k", { count: formatCompactNumber(safeCount) });
}

// ponytail: naive diacritic fold for Vietnamese client-side search.
// Ceiling: only folds Vietnamese combining marks + đ/Đ; other scripts pass through.
function normalizeVietnamese(input: string): string {
	return input
		.normalize("NFD")
		.replace(/[\u0300-\u036f]/g, "")
		.replace(/đ/g, "d")
		.replace(/Đ/g, "D")
		.toLowerCase();
}

export function PlaybooksContent({ workspaceId }: PlaybooksContentProps) {
	const t = useTranslations("playbooks");
	const [selectedCategory, setSelectedCategory] = useState<string>("all");
	const { data, isLoading, error } = useAtomValue(playbooksListAtom(selectedCategory));
	const [selectedPlaybook, setSelectedPlaybook] = useState<PlaybookSummary | null>(null);
	const [searchQuery, setSearchQuery] = useState<string>("");

	const { data: workspace } = useQuery({
		queryKey: [...cacheKeys.workspaces.detail(String(workspaceId))],
		queryFn: () => workspacesApiService.getWorkspace({ id: workspaceId }),
		enabled: !!workspaceId,
	});

	useEffect(() => {
		if (workspace) {
			const mapped = mapWorkspaceVerticalToCategory(workspace.vertical);
			setSelectedCategory((current) => (current === "all" ? mapped : current));
		}
	}, [workspace]);

	const playbooks = data?.items ?? [];

	const filteredPlaybooks = useMemo(() => {
		const query = normalizeVietnamese(searchQuery.trim());
		return playbooks.filter((p) => {
			const matchCategory = selectedCategory === "all" || p.verticals.includes(selectedCategory);
			const haystack = [p.name, p.description ?? "", p.author_name ?? "", ...(p.tags ?? [])].map(
				normalizeVietnamese
			);
			const matchSearch = query === "" || haystack.some((text) => text.includes(query));
			return matchCategory && matchSearch;
		});
	}, [playbooks, selectedCategory, searchQuery]);

	if (isLoading) {
		return (
			<div className="flex items-center justify-center py-20">
				<Spinner className="h-8 w-8 text-primary" />
			</div>
		);
	}

	if (error) {
		return (
			<div className="rounded-xl border border-destructive/20 bg-destructive/5 p-8 text-center">
				<h2 className="text-base font-semibold text-destructive">{t("error_load_title")}</h2>
				<p className="mt-1 text-sm text-muted-foreground">{error.message}</p>
			</div>
		);
	}

	return (
		<div className="space-y-8">
			{/* Header Section */}
			<div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
				<div>
					<div className="flex items-center gap-2">
						<h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
							{t("marketplace_title")}
						</h1>
						<Badge
							variant="outline"
							className="border-primary/40 bg-primary/10 text-primary text-xs font-semibold"
						>
							{t("badge_official_verified")}
						</Badge>
					</div>
					<p className="mt-1 text-sm text-muted-foreground">{t("marketplace_desc")}</p>
				</div>
				<Badge variant="secondary" className="self-start md:self-auto font-mono text-xs px-3 py-1">
					{t("templates_count", { count: playbooks.length })}
				</Badge>
			</div>

			{/* Search & Category Tabs */}
			<div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<div className="flex flex-wrap items-center gap-2">
					{CATEGORIES_CONFIG.map((cat) => {
						const Icon = cat.icon;
						const isSelected = selectedCategory === cat.id;
						return (
							<Button
								key={cat.id}
								variant={isSelected ? "default" : "outline"}
								size="sm"
								onClick={() => setSelectedCategory(cat.id)}
								className={`gap-1.5 text-xs transition-all ${
									isSelected
										? "shadow-sm font-semibold"
										: "text-muted-foreground hover:text-foreground"
								}`}
							>
								<Icon className="h-3.5 w-3.5" aria-hidden="true" />
								{t(cat.labelKey)}
							</Button>
						);
					})}
				</div>

				<div className="relative w-full sm:w-64">
					<Search
						className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground"
						aria-hidden="true"
					/>
					<Input
						type="search"
						placeholder={t("search_placeholder")}
						value={searchQuery}
						onChange={(e) => setSearchQuery(e.target.value)}
						className="h-9 pl-9 text-xs"
					/>
				</div>
			</div>

			{/* Playbook Cards Grid */}
			{playbooks.length === 0 ? (
				<div className="rounded-xl border border-dashed border-border/80 bg-muted/20 p-12 text-center">
					<BookOpen className="mx-auto h-12 w-12 text-muted-foreground/60" aria-hidden />
					<h3 className="mt-4 text-base font-semibold text-foreground">{t("empty_title")}</h3>
					<p className="mt-1 text-sm text-muted-foreground max-w-sm mx-auto">{t("empty_desc")}</p>
				</div>
			) : filteredPlaybooks.length === 0 ? (
				<div className="rounded-xl border border-dashed border-border/80 bg-muted/20 p-12 text-center">
					<BookOpen className="mx-auto h-12 w-12 text-muted-foreground/60" aria-hidden />
					<h3 className="mt-4 text-base font-semibold text-foreground">{t("no_results_title")}</h3>
					<p className="mt-1 text-sm text-muted-foreground max-w-sm mx-auto">
						{t("no_results_desc")}
					</p>
				</div>
			) : (
				<div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
					{filteredPlaybooks.map((playbook) => {
						const isOfficial = playbook.scope === "system" || playbook.author_badge === "official";
						const AuthorIcon = isOfficial ? BadgeCheck : Building2;
						const badgeText = isOfficial
							? `Official${playbook.author_name ? ` · ${playbook.author_name}` : ""}`
							: `Workspace${playbook.author_name ? ` · ${playbook.author_name}` : ""}`;
						return (
							<Card
								key={playbook.id}
								className="group relative flex flex-col justify-between overflow-hidden rounded-xl border border-border/70 bg-card/60 backdrop-blur transition-all duration-200 hover:border-primary/50 hover:shadow-md hover:shadow-primary/5"
							>
								<CardHeader className="space-y-2 pb-3">
									<div className="flex items-center justify-between gap-2">
										<div className="flex flex-wrap gap-1.5">
											{playbook.verticals.map((v) => (
												<Badge
													key={v}
													variant="secondary"
													className="text-[10px] uppercase tracking-wider font-semibold bg-secondary/80 text-secondary-foreground"
												>
													{v}
												</Badge>
											))}
										</div>
										<div
											className={`flex items-center gap-1 text-[11px] font-medium ${
												isOfficial ? "text-primary" : "text-muted-foreground"
											}`}
										>
											<AuthorIcon
												className={`h-4 w-4 ${isOfficial ? "text-primary" : "text-muted-foreground"}`}
											/>
											<span className="truncate max-w-[120px]">{badgeText}</span>
										</div>
									</div>
									<CardTitle className="text-base font-bold leading-tight group-hover:text-primary transition-colors">
										{playbook.name}
									</CardTitle>
									<CardDescription className="text-xs line-clamp-3 text-muted-foreground leading-relaxed">
										{playbook.description}
									</CardDescription>
								</CardHeader>

								<CardFooter className="flex flex-col gap-3 pt-3 border-t border-border/40 bg-muted/10">
									<div className="flex items-center justify-between w-full text-xs text-muted-foreground">
										<div className="flex items-center gap-1">
											<Coins className="h-3.5 w-3.5 text-amber-500" aria-hidden="true" />
											<span className="font-semibold text-foreground">
												~{playbook.estimated_credits_cost ?? DEFAULT_CREDIT_COST}
											</span>{" "}
											{t("credits_per_run")}
										</div>
										<div className="flex items-center gap-1">
											<Flame className="h-3.5 w-3.5 text-orange-500" aria-hidden="true" />
											<span>{formatRunCount(playbook.run_count, t)}</span>
										</div>
									</div>

									<Button
										size="sm"
										className="w-full gap-1.5 font-medium shadow-sm transition-all group-hover:bg-primary"
										onClick={() => setSelectedPlaybook(playbook)}
									>
										<Play className="h-3.5 w-3.5 fill-current" aria-hidden="true" />
										{t("instantiate_btn")}
									</Button>
								</CardFooter>
							</Card>
						);
					})}
				</div>
			)}

			{selectedPlaybook && (
				<PlaybookInstantiateDialog
					playbook={selectedPlaybook}
					workspaceId={workspaceId}
					open={!!selectedPlaybook}
					onOpenChange={(open) => {
						if (!open) setSelectedPlaybook(null);
					}}
				/>
			)}
		</div>
	);
}
