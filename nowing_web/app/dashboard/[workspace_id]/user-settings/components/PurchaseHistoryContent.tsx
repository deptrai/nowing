"use client";

import { useQueries } from "@tanstack/react-query";
import { Coins, FileText, ReceiptText } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { CreditPurchase, PagePurchase, PurchaseStatus } from "@/contracts/types/stripe.types";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import { cn } from "@/lib/utils";

type PurchaseKind = "pages" | "credits";

type UnifiedPurchase = {
	id: string;
	kind: PurchaseKind;
	created_at: string;
	status: PurchaseStatus;
	/**
	 * Granted units. Interpretation depends on ``kind``:
	 *  - ``"pages"`` — integer number of indexed pages (legacy history).
	 *  - ``"credits"`` — integer micro-USD of credit (1_000_000 = $1.00).
	 * The ``Granted`` column formats accordingly.
	 */
	granted: number;
	amount_total: number | null;
	currency: string | null;
};

const statusStyles = (
	t: (k: string) => string
): Record<PurchaseStatus, { label: string; className: string }> => ({
	completed: {
		label: t("status_completed"),
		className: "bg-emerald-600 text-white border-transparent hover:bg-emerald-600",
	},
	pending: {
		label: t("status_pending"),
		className: "bg-yellow-600 text-white border-transparent hover:bg-yellow-600",
	},
	failed: {
		label: t("status_failed"),
		className: "bg-destructive text-white border-transparent hover:bg-destructive",
	},
});

const kindMeta = (
	t: (k: string) => string
): Record<
	PurchaseKind,
	{ label: string; icon: React.ComponentType<{ className?: string }>; iconClass: string }
> => ({
	pages: {
		label: t("pages"),
		icon: FileText,
		iconClass: "text-sky-500",
	},
	credits: {
		label: t("credits"),
		icon: Coins,
		iconClass: "text-amber-500",
	},
});

function formatDate(iso: string): string {
	return new Date(iso).toLocaleDateString(undefined, {
		year: "numeric",
		month: "short",
		day: "numeric",
	});
}

function formatAmount(amount: number | null, currency: string | null): string {
	if (amount == null) return "—";
	const dollars = amount / 100;
	const code = (currency ?? "usd").toUpperCase();
	return `$${dollars.toFixed(2)} ${code}`;
}

function normalizePagePurchase(p: PagePurchase): UnifiedPurchase {
	return {
		id: p.id,
		kind: "pages",
		created_at: p.created_at,
		status: p.status,
		granted: p.pages_granted,
		amount_total: p.amount_total,
		currency: p.currency,
	};
}

function normalizeCreditPurchase(p: CreditPurchase): UnifiedPurchase {
	return {
		id: p.id,
		kind: "credits",
		created_at: p.created_at,
		status: p.status,
		granted: p.credit_micros_granted,
		amount_total: p.amount_total,
		currency: p.currency,
	};
}

function formatGranted(p: UnifiedPurchase): string {
	if (p.kind === "credits") {
		const dollars = p.granted / 1_000_000;
		// Credit packs are always whole dollars today, but future fractional grants
		// such as refunds or low-balance refills shouldn't silently round to "$0".
		if (dollars >= 1) return `$${dollars.toFixed(2)} of credit`;
		if (dollars > 0) return `$${dollars.toFixed(3)} of credit`;
		return "$0 of credit";
	}
	return p.granted.toLocaleString();
}

export function PurchaseHistoryContent() {
	const t = useTranslations("userSettings");
	const STATUS_STYLES = statusStyles(t);
	const KIND_META = kindMeta(t);
	const results = useQueries({
		queries: [
			{
				queryKey: ["stripe-purchases"],
				queryFn: () => stripeApiService.getPagePurchases(),
			},
			{
				queryKey: ["stripe-credit-purchases"],
				queryFn: () => stripeApiService.getCreditPurchases(),
			},
		],
	});

	const [pagesQuery, creditsQuery] = results;
	const isLoading = pagesQuery.isLoading || creditsQuery.isLoading;

	const purchases = useMemo<UnifiedPurchase[]>(() => {
		const pagePurchases = pagesQuery.data?.purchases ?? [];
		const creditPurchases = creditsQuery.data?.purchases ?? [];
		return [
			...pagePurchases.map(normalizePagePurchase),
			...creditPurchases.map(normalizeCreditPurchase),
		].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
	}, [pagesQuery.data, creditsQuery.data]);

	if (isLoading) {
		return (
			<div className="flex items-center justify-center py-12">
				<Spinner size="md" className="text-muted-foreground" />
			</div>
		);
	}

	if (purchases.length === 0) {
		return (
			<div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
				<ReceiptText className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
				<p className="text-sm font-medium">{t("no_purchases")}</p>
				<p className="text-xs text-muted-foreground">{t("no_purchases_desc")}</p>
			</div>
		);
	}

	return (
		<div className="space-y-4">
			<div className="rounded-lg border">
				<Table>
					<TableHeader>
						<TableRow>
							<TableHead>{t("date")}</TableHead>
							<TableHead>{t("type")}</TableHead>
							<TableHead className="text-right">{t("granted")}</TableHead>
							<TableHead className="text-right">{t("amount")}</TableHead>
							<TableHead className="text-center">{t("status")}</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{purchases.map((p) => {
							const statusStyle = STATUS_STYLES[p.status];
							const kind = KIND_META[p.kind];
							const KindIcon = kind.icon;
							return (
								<TableRow key={`${p.kind}-${p.id}`}>
									<TableCell className="text-sm">{formatDate(p.created_at)}</TableCell>
									<TableCell className="text-sm">
										<div className="flex items-center gap-2">
											<KindIcon className={cn("h-4 w-4", kind.iconClass)} />
											<span>{kind.label}</span>
										</div>
									</TableCell>
									<TableCell className="text-right tabular-nums text-sm">
										{formatGranted(p)}
									</TableCell>
									<TableCell className="text-right tabular-nums text-sm">
										{formatAmount(p.amount_total, p.currency)}
									</TableCell>
									<TableCell className="text-center">
										<Badge className={cn("text-[10px]", statusStyle.className)}>
											{statusStyle.label}
										</Badge>
									</TableCell>
								</TableRow>
							);
						})}
					</TableBody>
				</Table>
			</div>
			<p className="text-center text-xs text-muted-foreground">
				Showing your {purchases.length} most recent purchase
				{purchases.length !== 1 ? "s" : ""}.
			</p>
		</div>
	);
}
