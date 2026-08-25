"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, PiggyBank, Save } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { UpdateWorkspaceLimitsRequest } from "@/contracts/types/workspace.types";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

interface AutoExtractBudgetCardProps {
	workspaceId: number;
}

function formatUsd(micros: number): string {
	const dollars = micros / 1_000_000;
	return Number.isFinite(dollars) ? dollars.toFixed(2) : "0.00";
}

function parseUsdToMicros(value: string): number | null {
	const parsed = Number.parseFloat(value);
	if (Number.isNaN(parsed) || parsed < 0) return null;
	return Math.round(parsed * 1_000_000);
}

export function AutoExtractBudgetCard({ workspaceId }: AutoExtractBudgetCardProps) {
	const t = useTranslations("usage");
	const queryClient = useQueryClient();

	const { data, isLoading } = useQuery({
		queryKey: cacheKeys.workspaces.limits(workspaceId),
		queryFn: () => workspacesApiService.getWorkspaceLimits(workspaceId),
		enabled: workspaceId > 0,
	});

	const [itemCap, setItemCap] = useState<string>("");
	const [spendCapDollars, setSpendCapDollars] = useState<string>("");
	const [walletPreCheck, setWalletPreCheck] = useState<boolean>(true);

	useEffect(() => {
		if (!data) return;
		setItemCap(data.auto_extract_item_cap?.toString() ?? "");
		setSpendCapDollars(
			data.auto_extract_spend_cap_micros != null
				? formatUsd(data.auto_extract_spend_cap_micros)
				: ""
		);
		setWalletPreCheck(data.auto_extract_wallet_pre_check ?? true);
	}, [data]);

	const mutation = useMutation({
		mutationFn: (body: Omit<UpdateWorkspaceLimitsRequest, "id">) =>
			workspacesApiService.updateWorkspaceLimits({ id: workspaceId, ...body }),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: cacheKeys.workspaces.limits(workspaceId) });
			toast.success(t("auto_extract_budget_saved"));
		},
		onError: () => {
			toast.error(t("auto_extract_budget_save_failed"));
		},
	});

	const handleSave = () => {
		const payload: Omit<UpdateWorkspaceLimitsRequest, "id"> = {};

		const parsedItemCap = itemCap.trim() === "" ? null : Number.parseInt(itemCap, 10);
		if (Number.isFinite(parsedItemCap) && parsedItemCap != null && parsedItemCap >= 0) {
			payload.auto_extract_item_cap = parsedItemCap === 0 ? null : parsedItemCap;
		} else if (
			itemCap.trim() !== "" &&
			(Number.isNaN(parsedItemCap as number) || (parsedItemCap as number) < 0)
		) {
			toast.error(t("auto_extract_item_cap_invalid"));
			return;
		}

		const parsedSpendCap = spendCapDollars.trim() === "" ? null : parseUsdToMicros(spendCapDollars);
		if (parsedSpendCap != null) {
			payload.auto_extract_spend_cap_micros = parsedSpendCap === 0 ? null : parsedSpendCap;
		} else if (spendCapDollars.trim() !== "") {
			toast.error(t("auto_extract_spend_cap_invalid"));
			return;
		}

		payload.auto_extract_wallet_pre_check = walletPreCheck;

		mutation.mutate(payload);
	};

	if (isLoading || !data) {
		return null;
	}

	const periodSpend = data.auto_extract_usage?.period_spend_micros ?? 0;
	const periodCount = data.auto_extract_usage?.period_count ?? 0;

	const spendCap = data.auto_extract_spend_cap_micros;
	const countCap = data.auto_extract_item_cap;

	const spendPercent = spendCap != null && spendCap > 0 ? (periodSpend / spendCap) * 100 : 0;
	const countPercent = countCap != null && countCap > 0 ? (periodCount / countCap) * 100 : 0;

	const showSpendWarning = spendPercent >= 80 && spendPercent < 100;
	const showCountWarning = countPercent >= 80 && countPercent < 100;

	return (
		<Card>
			<CardHeader>
				<div className="flex items-center gap-2">
					<PiggyBank className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
					<CardTitle className="text-base font-medium">{t("auto_extract_budget_title")}</CardTitle>
				</div>
				<CardDescription>{t("auto_extract_budget_description")}</CardDescription>
			</CardHeader>
			<CardContent className="space-y-4">
				{(showSpendWarning || showCountWarning) && (
					<Alert variant="warning">
						<AlertTriangle className="h-4 w-4" aria-hidden="true" />
						<AlertTitle>{t("auto_extract_budget_warning_title")}</AlertTitle>
						<AlertDescription>
							{showSpendWarning &&
								t("auto_extract_spend_warning", {
									spent: formatUsd(periodSpend),
									cap: formatUsd(spendCap ?? 0),
								})}
							{showSpendWarning && showCountWarning && <br />}
							{showCountWarning &&
								t("auto_extract_count_warning", {
									count: periodCount,
									cap: countCap ?? 0,
								})}
						</AlertDescription>
					</Alert>
				)}

				<div className="grid gap-4 sm:grid-cols-2">
					<div className="space-y-2">
						<Label htmlFor="auto-extract-item-cap">{t("auto_extract_item_cap_label")}</Label>
						<Input
							id="auto-extract-item-cap"
							type="number"
							min={0}
							placeholder={t("auto_extract_cap_placeholder")}
							value={itemCap}
							onChange={(e) => setItemCap(e.target.value)}
						/>
						<p className="text-xs text-muted-foreground">{t("auto_extract_item_cap_hint")}</p>
					</div>

					<div className="space-y-2">
						<Label htmlFor="auto-extract-spend-cap">{t("auto_extract_spend_cap_label")}</Label>
						<Input
							id="auto-extract-spend-cap"
							type="number"
							min={0}
							step={0.01}
							placeholder={t("auto_extract_spend_cap_placeholder")}
							value={spendCapDollars}
							onChange={(e) => setSpendCapDollars(e.target.value)}
						/>
						<p className="text-xs text-muted-foreground">{t("auto_extract_spend_cap_hint")}</p>
					</div>
				</div>

				<div className="flex items-center justify-between rounded-lg border p-3">
					<div className="space-y-0.5">
						<Label htmlFor="auto-extract-wallet-pre-check" className="text-sm font-medium">
							{t("auto_extract_wallet_pre_check_label")}
						</Label>
						<p className="text-xs text-muted-foreground">
							{t("auto_extract_wallet_pre_check_hint")}
						</p>
					</div>
					<Switch
						id="auto-extract-wallet-pre-check"
						checked={walletPreCheck}
						onCheckedChange={setWalletPreCheck}
					/>
				</div>

				<div className="flex items-center gap-2">
					<Button onClick={handleSave} disabled={mutation.isPending} size="sm">
						<Save className="mr-2 h-4 w-4" aria-hidden="true" />
						{mutation.isPending ? t("auto_extract_budget_saving") : t("auto_extract_budget_save")}
					</Button>
				</div>
			</CardContent>
		</Card>
	);
}
