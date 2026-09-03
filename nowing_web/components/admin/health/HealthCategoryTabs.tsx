"use client";

import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { HealthOverviewResponse } from "@/lib/apis/admin-health-api.service";

interface HealthCategoryTabsProps {
	categories: string[];
	selectedCategory: string;
	onSelectCategory: (category: string) => void;
	overview: HealthOverviewResponse | null;
}

export default function HealthCategoryTabs({
	categories,
	selectedCategory,
	onSelectCategory,
	overview,
}: HealthCategoryTabsProps) {
	const categoryMeta = overview?.categories || {};

	const formatCategoryTitle = (cat: string) => {
		switch (cat) {
			case "all":
				return "All Services";
			case "infra":
				return "Infrastructure";
			case "model":
				return "AI Models";
			case "scraper":
				return "Scrapers";
			case "connector":
				return "Connectors";
			case "proxy":
				return "Proxies";
			case "research":
				return "ChainLens";
			default:
				return cat.charAt(0).toUpperCase() + cat.slice(1);
		}
	};

	const allList = ["all", ...categories.filter((c) => c !== "all")];

	return (
		<div className="overflow-x-auto pb-1" data-testid="health-category-tabs">
			<Tabs value={selectedCategory} onValueChange={onSelectCategory} className="w-full">
				<TabsList className="h-10">
					{allList.map((cat) => {
						const meta = cat === "all" ? null : categoryMeta[cat];
						const hasAlert =
							cat === "all"
								? (overview?.status_counts?.unavailable || 0) +
										(overview?.status_counts?.degraded || 0) >
									0
								: (meta?.unavailable || 0) + (meta?.degraded || 0) > 0;

						return (
							<TabsTrigger
								key={cat}
								value={cat}
								className="flex items-center gap-1.5 px-3"
								data-testid={`tab-category-${cat}`}
							>
								<span>{formatCategoryTitle(cat)}</span>
								{hasAlert && <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />}
								{meta && (
									<Badge variant="secondary" className="text-[10px] h-4 px-1 ml-1">
										{meta.total}
									</Badge>
								)}
							</TabsTrigger>
						);
					})}
				</TabsList>
			</Tabs>
		</div>
	);
}
