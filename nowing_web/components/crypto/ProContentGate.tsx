"use client";

import { Lock, Zap } from "lucide-react";
import Link from "next/link";
import type React from "react";
import { useSubscriptionGate } from "@/hooks/use-subscription-gate";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface ProContentGateProps {
	children: React.ReactNode;
	className?: string;
	title?: string;
	description?: string;
}

/**
 * Wraps gated content with a Pro-subscription paywall.
 *
 * - Pro user: render children verbatim.
 * - Free user (online): render blurred preview + upgrade CTA.
 *   Children are wrapped with `inert + aria-hidden + tabIndex=-1` so a
 *   keyboard user cannot Tab into interactive controls behind the blur and
 *   trigger paid actions (e.g. firing the scenario re-synthesize).
 * - Free user (offline): render children unchanged (AC#6, accepted trade-off).
 * - Loading state: render the redacted view *immediately* — never block page
 *   load with a skeleton (spec anti-pattern).
 */
export function ProContentGate({
	children,
	className,
	title = "Pro Research Content",
	description = "Upgrade to Pro to access full depth research, AI insights and scenario analysis.",
}: ProContentGateProps) {
	const { isPro, isLoading } = useSubscriptionGate();

	const isOffline = typeof navigator !== "undefined" && !navigator.onLine;

	// AC#6: offline → no enforcement.
	if (isOffline) {
		return <>{children}</>;
	}

	// Pro (or, while loading, treat children as gated rather than blocking the
	// page with a skeleton — matches spec anti-pattern "KHÔNG block page load").
	if (isPro) {
		return <>{children}</>;
	}

	// Either confirmed not-Pro, OR still loading the user record. In both cases
	// we render the redacted view immediately. When `isLoading` resolves to
	// `isPro=true` the component re-renders and unblurs.
	const ariaLabel = isLoading
		? "Loading subscription status — Pro content gated by default"
		: "Pro content. Upgrade to view.";

	return (
		<div
			className={cn("relative overflow-hidden rounded-xl border bg-card", className)}
			aria-label={ariaLabel}
		>
			{/* Blurred children. `inert` blocks keyboard focus, mouse events, and
			   programmatic focus on the entire subtree — preventing the documented
			   bypass where a free user could Tab into the simulator and fire
			   paid actions despite the visual blur. */}
			<div
				// `inert` blocks keyboard focus / mouse events / programmatic
				// focus on the entire subtree. Spread via an object so the
				// types check across both React 18 and React 19 (where
				// `inert` is a typed boolean prop).
				{...{ inert: true }}
				aria-hidden="true"
				tabIndex={-1}
				className="pointer-events-none select-none opacity-40 blur-[8px]"
			>
				{children}
			</div>

			{/* Upgrade Prompt Overlay */}
			<div className="absolute inset-0 flex items-center justify-center p-6 bg-background/20 backdrop-blur-[2px]">
				<Card className="w-full max-w-sm border-primary/20 shadow-2xl shadow-primary/10">
					<CardHeader className="text-center pb-2">
						<div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
							<Lock className="h-6 w-6" />
						</div>
						<CardTitle className="text-xl font-bold">{title}</CardTitle>
						<CardDescription className="text-sm">{description}</CardDescription>
					</CardHeader>
					<CardContent className="flex flex-col gap-3 pt-4">
						<Button asChild className="w-full font-semibold gap-2">
							<Link href="/pricing">
								<Zap className="h-4 w-4 fill-current" />
								Upgrade to Pro
							</Link>
						</Button>
						<p className="text-[10px] text-center text-muted-foreground uppercase tracking-wider font-medium">
							Instant access • Cancel anytime
						</p>
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
