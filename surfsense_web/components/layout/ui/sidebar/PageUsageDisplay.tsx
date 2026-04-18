"use client";

import { useQuery } from "@tanstack/react-query";
import { CreditCard, Settings, Zap } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { stripeApiService } from "@/lib/apis/stripe-api.service";

interface PageUsageDisplayProps {
	pagesUsed: number;
	pagesLimit: number;
	tokensUsed: number;
	tokensLimit: number;
	purchasedTokens?: number;
	planId?: string;
	subscriptionStatus?: string;
}

function formatTokenCount(n: number): string {
	if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
	if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
	return n.toLocaleString();
}

function progressColor(percent: number): string {
	if (percent > 95) return "[&>div]:bg-red-500";
	if (percent > 80) return "[&>div]:bg-amber-500";
	return "";
}

export function PageUsageDisplay({
	pagesUsed,
	pagesLimit,
	tokensUsed,
	tokensLimit,
	purchasedTokens = 0,
	planId = "free",
	subscriptionStatus = "free",
}: PageUsageDisplayProps) {
	const params = useParams();
	const searchSpaceId = params?.search_space_id ?? "";
	const pagePercent = pagesLimit > 0 ? Math.min(100, (pagesUsed / pagesLimit) * 100) : 0;

	const effectiveTokenLimit = tokensLimit + purchasedTokens;
	const tokenPercent =
		effectiveTokenLimit > 0 ? Math.min(100, (tokensUsed / effectiveTokenLimit) * 100) : 0;

	const { data: stripeStatus } = useQuery({
		queryKey: ["stripe-status"],
		queryFn: () => stripeApiService.getStatus(),
	});
	const stripeEnabled = stripeStatus?.stripe_enabled ?? false;

	const isPro = subscriptionStatus === "active";
	const [portalLoading, setPortalLoading] = useState(false);

	const handleManageBilling = async () => {
		if (portalLoading) return;
		setPortalLoading(true);
		try {
			const res = await stripeApiService.getBillingPortal();
			if (res.url) window.location.href = res.url;
		} catch {
			toast.error("Unable to open billing portal. Please try again.");
		} finally {
			setPortalLoading(false);
		}
	};

	return (
		<div className="px-3 py-3 border-t">
			<div className="space-y-2">
				{/* Plan badge */}
				<div className="flex items-center justify-between text-xs">
					<span className="text-muted-foreground font-medium">
						{isPro ? (planId === "pro_yearly" ? "PRO YEARLY" : "PRO MONTHLY") : "FREE"}
					</span>
					<Badge
						className={`h-4 rounded px-1 text-[10px] font-semibold leading-none border-transparent ${
							isPro
								? "bg-primary text-primary-foreground hover:bg-primary"
								: "bg-muted text-muted-foreground hover:bg-muted"
						}`}
					>
						{isPro ? "PRO" : "FREE"}
					</Badge>
				</div>

				{/* Page usage */}
				<div className="space-y-1">
					<div className="flex justify-between items-center text-xs">
						<span className="text-muted-foreground">
							{pagesUsed.toLocaleString()} / {pagesLimit.toLocaleString()} pages ETL
						</span>
						<span className="font-medium">{pagePercent.toFixed(0)}%</span>
					</div>
					<Progress value={pagePercent} className={`h-1.5 ${progressColor(pagePercent)}`} />
				</div>

				{/* Token usage */}
				<div className="space-y-1">
					<div className="flex justify-between items-center text-xs">
						<span className="text-muted-foreground">
							{formatTokenCount(tokensUsed)} / {formatTokenCount(effectiveTokenLimit)} tokens
							{purchasedTokens > 0 && (
								<span className="text-primary"> (+{formatTokenCount(purchasedTokens)})</span>
							)}
						</span>
						<span className="font-medium">{tokenPercent.toFixed(0)}%</span>
					</div>
					<Progress value={tokenPercent} className={`h-1.5 ${progressColor(tokenPercent)}`} />
				</div>

				{/* Get Free Pages incentive */}
				<Link
					href={`/dashboard/${searchSpaceId}/more-pages`}
					className="group flex w-[calc(100%+0.75rem)] items-center justify-between rounded-md px-1.5 py-1 -mx-1.5 transition-colors hover:bg-accent"
				>
					<span className="flex items-center gap-1.5 text-xs text-muted-foreground group-hover:text-accent-foreground">
						<Zap className="h-3 w-3 shrink-0" />
						Get Free Pages
					</span>
					<Badge className="h-4 rounded px-1 text-[10px] font-semibold leading-none bg-emerald-600 text-white border-transparent hover:bg-emerald-600">
						FREE
					</Badge>
				</Link>

				{/* Buy More Tokens (PAYG) */}
				{stripeEnabled && (
					<Link
						href={`/dashboard/${searchSpaceId}/buy-tokens`}
						className="group flex w-[calc(100%+0.75rem)] items-center justify-between rounded-md px-1.5 py-1 -mx-1.5 transition-colors hover:bg-accent"
					>
						<span className="flex items-center gap-1.5 text-xs text-muted-foreground group-hover:text-accent-foreground">
							<CreditCard className="h-3 w-3 shrink-0" />
							Buy More Tokens
						</span>
						<span className="text-[10px] font-medium text-muted-foreground">from $1</span>
					</Link>
				)}

				{/* Upgrade to Pro (free users) or Manage Billing (pro users) */}
				{!isPro ? (
					<Link
						href="/pricing"
						className="group flex w-[calc(100%+0.75rem)] items-center justify-between rounded-md px-1.5 py-1 -mx-1.5 transition-colors hover:bg-accent"
					>
						<span className="flex items-center gap-1.5 text-xs text-muted-foreground group-hover:text-accent-foreground">
							<Zap className="h-3 w-3 shrink-0 text-primary" />
							Upgrade to Pro
						</span>
						<Badge className="h-4 rounded px-1 text-[10px] font-semibold leading-none bg-primary text-primary-foreground border-transparent hover:bg-primary">
							PRO
						</Badge>
					</Link>
				) : stripeEnabled ? (
					<button
						type="button"
						onClick={handleManageBilling}
						disabled={portalLoading}
						className="group flex w-[calc(100%+0.75rem)] items-center justify-between rounded-md px-1.5 py-1 -mx-1.5 transition-colors hover:bg-accent disabled:opacity-50 text-left"
					>
						<span className="flex items-center gap-1.5 text-xs text-muted-foreground group-hover:text-accent-foreground">
							<Settings className="h-3 w-3 shrink-0" />
							{portalLoading ? "Opening…" : "Manage Billing"}
						</span>
					</button>
				) : null}
			</div>
		</div>
	);
}
