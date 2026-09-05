"use client";

import { useQuery } from "@tanstack/react-query";
import {
	Bell,
	Building2,
	CheckCircle2,
	Clock,
	LineChart,
	Newspaper,
	Plus,
	Search,
	ShoppingBag,
	Tag,
} from "lucide-react";
import { useState } from "react";
import CreateFromTemplateModal from "@/components/alerts/CreateFromTemplateModal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { AlertRule } from "@/contracts/types/alert-rules.types";
import { baseApiService } from "@/lib/apis/base-api.service";

interface SavedSearchesListContentProps {
	workspaceId: number;
}

export function SavedSearchesListContent({ workspaceId }: SavedSearchesListContentProps) {
	const [templateModalOpen, setTemplateModalOpen] = useState(false);

	const {
		data: rules = [],
		isLoading,
		refetch,
	} = useQuery<AlertRule[], Error>({
		queryKey: ["alert-rules", workspaceId],
		queryFn: () => baseApiService.get(`/workspaces/${workspaceId}/alert-rules`),
		staleTime: 30_000,
	});

	const getCategoryIcon = (cap: string) => {
		if (cap.includes("cafef") || cap.includes("vietstock")) {
			return <LineChart className="h-4 w-4 text-emerald-500" />;
		}
		if (cap.includes("news") || cap.includes("google")) {
			return <Newspaper className="h-4 w-4 text-sky-500" />;
		}
		if (cap.includes("masothue")) {
			return <Building2 className="h-4 w-4 text-amber-500" />;
		}
		if (cap.includes("shopee") || cap.includes("ecommerce")) {
			return <ShoppingBag className="h-4 w-4 text-rose-500" />;
		}
		return <Bell className="h-4 w-4 text-primary" />;
	};

	return (
		<div className="p-6 space-y-6 max-w-7xl mx-auto">
			<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
				<div>
					<h1 className="text-2xl font-bold tracking-tight">Saved Searches & Alert Rules</h1>
					<p className="text-sm text-muted-foreground">
						Automated continuous research monitoring for news, stock prices, corporate changes, and
						e-commerce.
					</p>
				</div>
				<div className="flex items-center gap-2.5">
					<Button
						onClick={() => setTemplateModalOpen(true)}
						className="gap-2 text-xs h-9"
						data-testid="btn-open-template-modal"
					>
						<Tag className="h-4 w-4" />
						Create from Template
					</Button>
				</div>
			</div>

			{isLoading ? (
				<div className="py-16 text-center text-sm text-muted-foreground animate-pulse">
					Loading alert rules...
				</div>
			) : rules.length === 0 ? (
				<div className="text-center py-16 border border-dashed rounded-xl space-y-4 bg-muted/10">
					<div className="mx-auto w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary">
						<Search className="h-6 w-6" />
					</div>
					<div className="space-y-1">
						<h3 className="font-semibold text-base">No active alert rules yet</h3>
						<p className="text-xs text-muted-foreground max-w-md mx-auto">
							Activate 1-click intelligent monitoring for Vietnam stocks, business registry updates,
							or e-commerce price drops.
						</p>
					</div>
					<Button
						onClick={() => setTemplateModalOpen(true)}
						variant="outline"
						size="sm"
						className="gap-2"
						data-testid="btn-empty-create-template"
					>
						<Plus className="h-4 w-4" />
						Browse Vertical Templates
					</Button>
				</div>
			) : (
				<div
					className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
					data-testid="alert-rules-grid"
				>
					{rules.map((rule) => (
						<Card key={rule.id} className="hover:shadow-xs transition-shadow">
							<CardContent className="p-5 space-y-3">
								<div className="flex items-start justify-between gap-2">
									<div className="flex items-center gap-2 min-w-0">
										<div className="p-1.5 rounded-md bg-muted/60 shrink-0">
											{getCategoryIcon(rule.capability_id)}
										</div>
										<h4 className="font-semibold text-sm truncate" title={rule.name}>
											{rule.name}
										</h4>
									</div>
									<Badge
										variant={rule.enabled ? "default" : "outline"}
										className="text-[10px] shrink-0"
									>
										{rule.enabled ? "Active" : "Paused"}
									</Badge>
								</div>

								<div className="text-xs text-muted-foreground space-y-1">
									<p className="truncate">
										Capability: <code className="text-foreground">{rule.capability_id}</code>
									</p>
									<p>
										Strategy:{" "}
										<span className="font-medium text-foreground">{rule.diff_strategy}</span>
									</p>
								</div>

								<div className="flex items-center justify-between text-[11px] text-muted-foreground pt-2 border-t">
									<span className="flex items-center gap-1">
										<Clock className="h-3 w-3" />
										Schedule: {rule.schedule}
									</span>
									<span className="flex items-center gap-1">
										<CheckCircle2 className="h-3 w-3 text-emerald-500" />
										{rule.notification_channels.join(", ")}
									</span>
								</div>
							</CardContent>
						</Card>
					))}
				</div>
			)}

			<CreateFromTemplateModal
				workspaceId={workspaceId}
				open={templateModalOpen}
				onOpenChange={setTemplateModalOpen}
				onCreated={() => refetch()}
			/>
		</div>
	);
}
