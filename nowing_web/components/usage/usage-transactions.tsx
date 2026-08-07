"use client";

import { useTranslations } from "next-intl";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { UsageTransactionItem } from "@/contracts/types/usage.types";

function formatUsdMicros(micros: number): string {
	const dollars = micros / 1_000_000;
	if (dollars === 0) return "$0";
	if (Math.abs(dollars) >= 1) return `$${Math.abs(dollars).toFixed(2)}`;
	return `$${Math.abs(dollars).toFixed(3)}`;
}

function formatDate(iso: string): string {
	return new Date(iso).toLocaleDateString();
}

interface UsageTransactionsProps {
	transactions: UsageTransactionItem[];
	isLoading: boolean;
}

export function UsageTransactions({ transactions, isLoading }: UsageTransactionsProps) {
	const t = useTranslations("usage");

	return (
		<Card>
			<CardHeader>
				<CardTitle>{t("transactions_title")}</CardTitle>
				<CardDescription>{t("transactions_description")}</CardDescription>
			</CardHeader>
			<CardContent>
				{isLoading ? (
					<Skeleton className="h-32 w-full" />
				) : transactions.length === 0 ? (
					<p className="text-sm text-muted-foreground">{t("no_transactions")}</p>
				) : (
					<ul className="divide-y">
						{transactions.map((tx) => (
							<li
								key={`${tx.type}-${tx.created_at}-${tx.description ?? ""}-${tx.status ?? ""}`}
								data-testid="transaction-row"
								className="flex items-center justify-between py-3"
							>
								<div>
									<p className="text-sm font-medium capitalize">{tx.type.replace(/_/g, " ")}</p>
									<p className="text-xs text-muted-foreground">{tx.description || "—"}</p>
								</div>
								<div className="text-right">
									<p className="text-sm tabular-nums font-medium">
										{tx.amount_micros >= 0 ? "+" : "-"}
										{formatUsdMicros(tx.amount_micros)}
									</p>
									<p className="text-xs text-muted-foreground">{formatDate(tx.created_at)}</p>
								</div>
							</li>
						))}
					</ul>
				)}
			</CardContent>
		</Card>
	);
}
