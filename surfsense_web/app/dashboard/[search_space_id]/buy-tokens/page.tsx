"use client";

import { useAtomValue } from "jotai";
import { Minus, Plus, Zap } from "lucide-react";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { stripeApiService } from "@/lib/apis/stripe-api.service";

const TOKENS_PER_USD = 100_000;
const MIN_USD = 1;

function formatTokens(n: number): string {
	if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n % 1_000_000 === 0 ? 0 : 1)}M`;
	if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
	return n.toLocaleString();
}

const QUICK_AMOUNTS = [
	{ usd: 1, label: "$1", tokens: "100K" },
	{ usd: 5, label: "$5", tokens: "500K" },
	{ usd: 10, label: "$10", tokens: "1M" },
	{ usd: 25, label: "$25", tokens: "2.5M" },
	{ usd: 50, label: "$50", tokens: "5M" },
	{ usd: 100, label: "$100", tokens: "10M" },
];

export default function BuyTokensPage() {
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id ?? 0);
	const userQuery = useAtomValue(currentUserAtom);
	const user = userQuery.data;

	const [amountStr, setAmountStr] = useState("5");
	const [isLoading, setIsLoading] = useState(false);

	const amountUsd = useMemo(() => {
		const n = parseFloat(amountStr);
		return Number.isFinite(n) && n > 0 ? n : 0;
	}, [amountStr]);

	const tokensGranted = useMemo(() => Math.round(amountUsd * TOKENS_PER_USD), [amountUsd]);

	const monthlyLimit = user?.monthly_token_limit ?? 0;
	const purchasedTokens = user?.purchased_tokens ?? 0;
	const tokensUsed = user?.tokens_used_this_month ?? 0;
	const totalLimit = monthlyLimit + purchasedTokens;
	const available = Math.max(0, totalLimit - tokensUsed);

	const handleBuy = async () => {
		if (isLoading || amountUsd < MIN_USD) return;
		setIsLoading(true);
		try {
			const res = await stripeApiService.createTokenTopupCheckout({
				amount_usd: amountUsd,
				search_space_id: searchSpaceId,
			});
			if (res.admin_approval_mode) {
				toast.info(
					"Stripe is not configured. Contact your admin to have tokens added to your account.",
					{ duration: 8000 }
				);
				return;
			}
			if (res.checkout_url) {
				window.location.href = res.checkout_url;
			}
		} catch {
			toast.error("Unable to start checkout. Please try again.");
		} finally {
			setIsLoading(false);
		}
	};

	const handleAdjust = (delta: number) => {
		const cur = parseFloat(amountStr) || 0;
		const next = Math.max(MIN_USD, Math.round((cur + delta) * 100) / 100);
		setAmountStr(String(next));
	};

	return (
		<div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4 py-8">
			<div className="w-full max-w-md space-y-6">
				{/* Header */}
				<div className="text-center space-y-1">
					<h1 className="text-2xl font-bold">Buy Token Top-up</h1>
					<p className="text-sm text-muted-foreground">
						Pay any amount. Rate: 100K tokens per $1 USD.
					</p>
					{user && (
						<p className="text-sm font-medium mt-2">
							Balance:{" "}
							<span className="text-primary">{formatTokens(available)} available</span>
							{purchasedTokens > 0 && (
								<span className="text-muted-foreground">
									{" "}(+{formatTokens(purchasedTokens)} purchased)
								</span>
							)}
						</p>
					)}
				</div>

				{/* Quick amount buttons */}
				<div className="space-y-2">
					<p className="text-xs text-center text-muted-foreground uppercase tracking-wide">
						Quick amounts
					</p>
					<div className="grid grid-cols-3 gap-2">
						{QUICK_AMOUNTS.map(({ usd, label, tokens }) => (
							<Button
								key={usd}
								variant={amountUsd === usd ? "default" : "outline"}
								size="sm"
								className="flex flex-col h-auto py-2 gap-0.5"
								onClick={() => setAmountStr(String(usd))}
							>
								<span className="font-bold">{label}</span>
								<span className="text-xs opacity-70">{tokens} tokens</span>
							</Button>
						))}
					</div>
				</div>

				{/* Custom amount card */}
				<Card>
					<CardHeader className="pb-3">
						<CardTitle className="text-base">Custom amount</CardTitle>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="flex items-center gap-2">
							<Button
								variant="outline"
								size="icon"
								className="shrink-0"
								onClick={() => handleAdjust(-1)}
								disabled={amountUsd <= MIN_USD}
							>
								<Minus className="h-4 w-4" />
							</Button>
							<div className="relative flex-1">
								<span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm select-none">
									$
								</span>
								<Input
									type="number"
									min={MIN_USD}
									step={1}
									value={amountStr}
									onChange={(e) => setAmountStr(e.target.value)}
									className="pl-7 text-center text-lg font-semibold"
								/>
							</div>
							<Button
								variant="outline"
								size="icon"
								className="shrink-0"
								onClick={() => handleAdjust(1)}
							>
								<Plus className="h-4 w-4" />
							</Button>
						</div>

						{/* Token preview */}
						{tokensGranted > 0 && (
							<div className="rounded-md bg-muted px-4 py-3 text-center space-y-0.5">
								<p className="text-2xl font-bold text-primary">
									{formatTokens(tokensGranted)} tokens
								</p>
								<p className="text-xs text-muted-foreground">added to your account</p>
							</div>
						)}

						<Button
							className="w-full"
							size="lg"
							disabled={isLoading || amountUsd < MIN_USD}
							onClick={handleBuy}
						>
							<Zap className="h-4 w-4 mr-2" />
							{isLoading
								? "Redirecting to checkout…"
								: amountUsd >= MIN_USD
									? `Buy ${formatTokens(tokensGranted)} tokens for $${amountUsd}`
									: "Enter an amount (min $1)"}
						</Button>
					</CardContent>
				</Card>

				<p className="text-center text-xs text-muted-foreground">
					Tokens expire at the end of your billing period. ETL page quota is set by your
					subscription plan.
				</p>
			</div>
		</div>
	);
}
