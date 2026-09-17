"use client";

import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import type { FinalizeCheckoutResponse } from "@/contracts/types/stripe.types";
import { stripeApiService } from "@/lib/apis/stripe-api.service";

type FinalizeState =
	| { kind: "loading" }
	| { kind: "completed"; data: FinalizeCheckoutResponse }
	| { kind: "pending"; data: FinalizeCheckoutResponse }
	| { kind: "still_pending"; data: FinalizeCheckoutResponse }
	| { kind: "failed"; data: FinalizeCheckoutResponse }
	| { kind: "error"; message: string }
	| { kind: "no_session" };

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_ATTEMPTS = 15; // ~30s total before falling back to the still_pending state

export default function PurchaseSuccessPage() {
	const params = useParams();
	const searchParams = useSearchParams();
	const t = useTranslations("purchase");
	const locale = useLocale();
	const workspaceId = String(params.workspace_id ?? "");
	const sessionId = searchParams.get("session_id");

	const [state, setState] = useState<FinalizeState>(
		sessionId ? { kind: "loading" } : { kind: "no_session" }
	);
	// Tracks active polling so component unmount cancels it
	const cancelledRef = useRef(false);

	useEffect(() => {
		if (!sessionId) return;

		cancelledRef.current = false;

		const poll = async (attempt: number): Promise<void> => {
			if (cancelledRef.current) return;
			try {
				const data = await stripeApiService.finalizeCheckout(sessionId);
				if (cancelledRef.current) return;

				if (data.status === "completed") {
					setState({ kind: "completed", data });
					return;
				}
				if (data.status === "failed") {
					setState({ kind: "failed", data });
					return;
				}

				// Status is "pending" - either the user paid via async
				// payment method (Klarna, ACH) or webhook + finalize both
				// raced and lost. Keep polling up to MAX_POLL_ATTEMPTS,
				// then fall back to a friendlier message that explains
				// fulfilment may complete asynchronously.
				if (attempt < MAX_POLL_ATTEMPTS) {
					setState({ kind: "pending", data });
					setTimeout(() => poll(attempt + 1), POLL_INTERVAL_MS);
				} else {
					setState({ kind: "still_pending", data });
				}
			} catch (err) {
				if (cancelledRef.current) return;
				const message =
					err instanceof Error ? err.message : t("finalize_error");
				setState({ kind: "error", message });
			}
		};

		void poll(1);

		return () => {
			cancelledRef.current = true;
		};
	}, [sessionId, t]);

	const titleKey = {
		loading: "title_confirming",
		pending: "title_processing",
		still_pending: "title_still_pending",
		completed: "title_complete",
		failed: "title_failed",
		error: "title_error",
		no_session: "title_complete",
	}[state.kind];

	const descKey = {
		loading: "desc_confirming",
		pending: "desc_processing",
		still_pending: "desc_still_pending",
		completed: null,
		failed: "desc_failed",
		error: "desc_error",
		no_session: "desc_no_session",
	}[state.kind];

	return (
		<div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4 py-8">
			<Card className="w-full max-w-lg">
				<CardHeader className="text-center">
					{state.kind === "loading" || state.kind === "pending" ? (
						<Loader2 className="mx-auto h-10 w-10 animate-spin text-primary" aria-hidden="true" />
					) : state.kind === "completed" ? (
						<CheckCircle2 className="mx-auto h-10 w-10 text-emerald-500" aria-hidden="true" />
					) : (
						<AlertCircle className="mx-auto h-10 w-10 text-amber-500" aria-hidden="true" />
					)}
					<CardTitle className="text-2xl">{t(titleKey)}</CardTitle>
					<CardDescription>
						{state.kind === "completed"
							? t("desc_completed", {
									credit: formatCredit(state.data.credit_micros_granted ?? 0, locale),
								})
							: descKey
								? t(descKey)
								: null}
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-3 text-center">
					{state.kind === "completed" && (
						<p className="text-sm text-muted-foreground">
							{t("new_balance", {
								balance: formatCredit(state.data.credit_micros_balance ?? 0, locale),
							})}
						</p>
					)}
					{state.kind === "error" && (
						<p className="text-sm text-muted-foreground">{state.message}</p>
					)}
				</CardContent>
				<CardFooter className="flex flex-col gap-2">
					<Button asChild className="w-full">
						<Link href={`/dashboard/${workspaceId}/new-chat`}>{t("back_to_dashboard")}</Link>
					</Button>
					<Button asChild variant="outline" className="w-full">
						<Link href={`/dashboard/${workspaceId}/buy-more`}>{t("buy_credits")}</Link>
					</Button>
				</CardFooter>
			</Card>
		</div>
	);
}

function formatCredit(micros: number, locale: string): string {
	const dollars = micros / 1_000_000;
	return new Intl.NumberFormat(locale, {
		style: "currency",
		currency: "USD",
		maximumFractionDigits: 2,
	}).format(dollars);
}
