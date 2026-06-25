"use client";

import { useAtomValue } from "jotai";
import { CreditCard, Zap } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { stripeApiService } from "@/lib/apis/stripe-api.service";

function formatTokens(n: number): string {
	if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
	if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
	return n.toLocaleString();
}

function progressColor(percent: number): string {
	if (percent > 95) return "[&>div]:bg-red-500";
	if (percent > 80) return "[&>div]:bg-amber-500";
	return "";
}

export function SubscriptionContent() {
	const params = useParams();
	const searchSpaceId = params?.search_space_id ?? "";
	const userQuery = useAtomValue(currentUserAtom);
	const user = userQuery.data;
	const [portalLoading, setPortalLoading] = useState(false);

	if (!user) return null;

	const isPro = user.subscription_status === "active";
	const planLabel =
		user.plan_id === "pro_yearly"
			? "Pro (Yearly)"
			: user.plan_id === "pro_monthly"
				? "Pro (Monthly)"
				: "Free";

	const monthlyLimit = user.monthly_token_limit ?? 0;
	const purchasedTokens = user.purchased_tokens ?? 0;
	const effectiveTokenLimit = monthlyLimit + purchasedTokens;
	const tokensUsed = user.tokens_used_this_month ?? 0;
	const tokenPercent =
		effectiveTokenLimit > 0 ? Math.min(100, (tokensUsed / effectiveTokenLimit) * 100) : 0;

	const pagePercent =
		user.pages_limit > 0 ? Math.min(100, (user.pages_used / user.pages_limit) * 100) : 0;

	const periodEnd = user.subscription_current_period_end
		? new Date(user.subscription_current_period_end).toLocaleDateString(undefined, {
				year: "numeric",
				month: "long",
				day: "numeric",
			})
		: null;

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
		<div className="space-y-6">
			{/* Plan */}
			<div className="space-y-2">
				<h3 className="text-sm font-semibold">Current Plan</h3>
				<div className="flex items-center gap-2">
					<Badge
						className={
							isPro
								? "bg-primary text-primary-foreground hover:bg-primary"
								: "bg-muted text-muted-foreground hover:bg-muted"
						}
					>
						{isPro ? "PRO" : "FREE"}
					</Badge>
					<span className="text-sm text-muted-foreground">{planLabel}</span>
				</div>
				{periodEnd && (
					<p className="text-xs text-muted-foreground">
						{isPro ? "Renews" : "Resets"} on {periodEnd}
					</p>
				)}
			</div>

			<Separator />

			{/* Usage */}
			<div className="space-y-4">
				<h3 className="text-sm font-semibold">Usage This Period</h3>

				{/* Pages ETL */}
				<div className="space-y-1.5">
					<div className="flex justify-between text-xs">
						<span className="text-muted-foreground">Pages ETL</span>
						<span>
							{user.pages_used.toLocaleString()} / {user.pages_limit.toLocaleString()}
						</span>
					</div>
					<Progress value={pagePercent} className={`h-1.5 ${progressColor(pagePercent)}`} />
				</div>

				{/* LLM Tokens */}
				<div className="space-y-1.5">
					<div className="flex justify-between text-xs">
						<span className="text-muted-foreground">LLM Tokens</span>
						<span>
							{formatTokens(tokensUsed)} / {formatTokens(effectiveTokenLimit)}
							{purchasedTokens > 0 && (
								<span className="text-primary ml-1">
									(+{formatTokens(purchasedTokens)} purchased)
								</span>
							)}
						</span>
					</div>
					<Progress value={tokenPercent} className={`h-1.5 ${progressColor(tokenPercent)}`} />
					<p className="text-[11px] text-muted-foreground">
						Monthly quota: {formatTokens(monthlyLimit)}
						{purchasedTokens > 0 && ` · Purchased: ${formatTokens(purchasedTokens)}`}
					</p>
				</div>
			</div>

			<Separator />

			{/* Actions */}
			<div className="space-y-2">
				<h3 className="text-sm font-semibold">Actions</h3>
				<div className="flex flex-col gap-2">
					<Button asChild variant="outline" size="sm" className="justify-start gap-2">
						<Link href={`/dashboard/${searchSpaceId}/buy-tokens`}>
							<Zap className="h-4 w-4" />
							Buy Token Top-up
						</Link>
					</Button>
					{!isPro && (
						<Button asChild size="sm" className="justify-start gap-2">
							<Link href="/pricing">
								<Zap className="h-4 w-4" />
								Upgrade to Pro
							</Link>
						</Button>
					)}
					{isPro && (
						<Button
							variant="outline"
							size="sm"
							className="justify-start gap-2"
							disabled={portalLoading}
							onClick={handleManageBilling}
						>
							<CreditCard className="h-4 w-4" />
							{portalLoading ? "Opening…" : "Manage Subscription"}
						</Button>
					)}
				</div>
			</div>
		</div>
	);
}
