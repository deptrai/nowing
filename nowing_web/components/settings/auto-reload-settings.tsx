"use client";

import { useQuery as useZeroQuery } from "@rocicorp/zero/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Info } from "lucide-react";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import { AppError } from "@/lib/error";
import { getWorkspaceIdNumber } from "@/lib/route-params";
import { queries } from "@/zero/queries";

const microsToDollars = (micros: number | null | undefined): string => {
	if (micros == null) return "";
	return (micros / 1_000_000).toString();
};

const dollarsToMicros = (value: string): number | null => {
	const trimmed = value.trim();
	if (trimmed === "") return null;
	const dollars = Number(trimmed);
	if (!Number.isFinite(dollars) || dollars < 0) return null;
	return Math.round(dollars * 1_000_000);
};

const formatUsd = (micros: number) => `$${(Math.max(0, micros) / 1_000_000).toFixed(2)}`;

export function AutoReloadSettings() {
	const t = useTranslations("settings");
	const params = useParams();
	const router = useRouter();
	const pathname = usePathname();
	const searchParams = useSearchParams();
	const queryClient = useQueryClient();
	const workspaceId = getWorkspaceIdNumber(params) ?? 0;

	const [enabled, setEnabled] = useState(false);
	const [thresholdInput, setThresholdInput] = useState("");
	const [amountInput, setAmountInput] = useState("");
	const seededRef = useRef(false);

	const [me] = useZeroQuery(queries.user.me({}));
	const balanceMicros = me?.creditMicrosBalance ?? 0;

	const { data: settings, isLoading } = useQuery({
		queryKey: ["auto-reload-settings"],
		queryFn: () => stripeApiService.getAutoReloadSettings(),
	});

	// Seed the form once from the server, then let the user own the inputs.
	useEffect(() => {
		if (settings && !seededRef.current) {
			seededRef.current = true;
			setEnabled(settings.enabled);
			setThresholdInput(microsToDollars(settings.threshold_micros));
			setAmountInput(microsToDollars(settings.amount_micros));
		}
	}, [settings]);

	// Surface the result of the Stripe card-setup redirect.
	useEffect(() => {
		const setupResult = searchParams.get("auto_reload_setup");
		if (!setupResult) return;
		if (setupResult === "success") {
			toast.success(t("topup_card_saved"));
			queryClient.invalidateQueries({ queryKey: ["auto-reload-settings"] });
		} else if (setupResult === "cancel") {
			toast.info(t("topup_card_setup_canceled"));
		}
		// Strip the query param so refreshes don't re-toast.
		router.replace(pathname);
	}, [searchParams, router, pathname, queryClient]);

	const setupMutation = useMutation({
		mutationFn: () => stripeApiService.createAutoReloadSetupSession({ workspace_id: workspaceId }),
		onSuccess: (response) => {
			window.location.assign(response.checkout_url);
		},
		onError: () => {
			toast.error(t("topup_start_card_setup_failed"));
		},
	});

	const saveMutation = useMutation({
		mutationFn: stripeApiService.updateAutoReloadSettings,
		onSuccess: (updated) => {
			queryClient.setQueryData(["auto-reload-settings"], updated);
			toast.success(updated.enabled ? t("topup_enabled_toast") : t("topup_settings_saved"));
		},
		onError: (error) => {
			if (error instanceof AppError && error.message) {
				toast.error(error.message);
				return;
			}
			toast.error(t("topup_save_failed"));
		},
	});

	// Render nothing while loading (avoids a spinner flash on pages where the
	// feature flag turns out to be off) and when top-ups are disabled
	// server-side.
	if (isLoading || !settings || !settings.feature_enabled) {
		return null;
	}

	const minAmountDollars = (settings.min_amount_micros / 1_000_000).toFixed(2);
	const hasCard = settings.has_payment_method;

	const handleSave = () => {
		if (!enabled) {
			saveMutation.mutate({
				enabled: false,
				threshold_micros: dollarsToMicros(thresholdInput),
				amount_micros: dollarsToMicros(amountInput),
			});
			return;
		}

		const thresholdMicros = dollarsToMicros(thresholdInput);
		const amountMicros = dollarsToMicros(amountInput);

		if (!thresholdMicros || thresholdMicros <= 0) {
			toast.error(t("topup_threshold_invalid"));
			return;
		}
		if (amountMicros == null || amountMicros < settings.min_amount_micros) {
			toast.error(t("topup_min_amount", { min: minAmountDollars }));
			return;
		}

		saveMutation.mutate({
			enabled: true,
			threshold_micros: thresholdMicros,
			amount_micros: amountMicros,
		});
	};

	const addCardButton = (
		<Button
			className="w-full sm:w-auto"
			onClick={() => setupMutation.mutate()}
			disabled={setupMutation.isPending}
		>
			{setupMutation.isPending ? (
				<>
					<Spinner size="xs" />
					{t("redirecting")}
				</>
			) : (
				t("add_card")
			)}
		</Button>
	);

	if (!hasCard) {
		return (
			<div className="space-y-5">
				{settings.failed_at && (
					<Alert variant="destructive">
						<AlertTriangle className="h-4 w-4" aria-hidden="true" />
						<AlertTitle>{t("topup_failed_title")}</AlertTitle>
						<AlertDescription>
							{t("topup_failed_desc")}
						</AlertDescription>
					</Alert>
				)}

				<div className="space-y-6">
					<Alert className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
						<div className="flex min-w-0 items-start gap-3">
							<Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
							<p className="text-sm leading-relaxed text-muted-foreground">
								{t.rich("topup_intro", {
									balance: formatUsd(balanceMicros),
									b: (chunks) => (
										<span className="font-medium text-foreground">{chunks}</span>
									),
								})}
							</p>
						</div>
						{addCardButton}
					</Alert>
					<Separator />
				</div>
			</div>
		);
	}

	return (
		<div className="space-y-6">
			{settings.failed_at && (
				<Alert variant="destructive">
					<AlertTriangle className="h-4 w-4" aria-hidden="true" />
					<AlertTitle>{t("topup_failed_title")}</AlertTitle>
					<AlertDescription>
						{t("topup_failed_desc")}
					</AlertDescription>
				</Alert>
			)}

			<section className="space-y-5">
				<div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
					<div className="space-y-1">
						<h2 className="text-base font-semibold tracking-tight">{t("auto_topups")}</h2>
						<p className="text-sm text-muted-foreground">
							{t.rich("topup_current_balance", {
								balance: formatUsd(balanceMicros),
								b: (chunks) => (
									<span className="font-medium text-foreground">{chunks}</span>
								),
							})}
						</p>
					</div>
					<Button
						className="w-full sm:w-auto"
						onClick={() => setupMutation.mutate()}
						disabled={setupMutation.isPending}
					>
						{setupMutation.isPending ? (
							<>
								<Spinner size="xs" />
								{t("redirecting")}
							</>
						) : (
							t("update_card")
						)}
					</Button>
				</div>

				<div className="flex items-center justify-between gap-4">
					<div className="space-y-0.5">
						<Label htmlFor="top-ups-toggle" className="text-sm font-medium">
							Enable top-ups
						</Label>
						<p className="text-xs text-muted-foreground">{t("enable_topups_desc")}</p>
					</div>
					<Switch id="top-ups-toggle" checked={enabled} onCheckedChange={setEnabled} />
				</div>

				<div className="grid gap-4 sm:grid-cols-2">
					<div className="space-y-1.5">
						<Label htmlFor="top-ups-threshold" className="text-xs">
							{t("topup_threshold_label")}
						</Label>
						<div className="relative">
							<span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
								$
							</span>
							<Input
								id="top-ups-threshold"
								type="number"
								min="0"
								step="1"
								inputMode="decimal"
								className="pl-6 tabular-nums"
								value={thresholdInput}
								onChange={(e) => setThresholdInput(e.target.value)}
								disabled={!enabled}
								placeholder="5"
							/>
						</div>
					</div>
					<div className="space-y-1.5">
						<Label htmlFor="top-ups-amount" className="text-xs">
							{t("topup_amount_label")}
						</Label>
						<div className="relative">
							<span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
								$
							</span>
							<Input
								id="top-ups-amount"
								type="number"
								min={minAmountDollars}
								step="1"
								inputMode="decimal"
								className="pl-6 tabular-nums"
								value={amountInput}
								onChange={(e) => setAmountInput(e.target.value)}
								disabled={!enabled}
								placeholder="10"
							/>
						</div>
						<p className="text-[11px] text-muted-foreground">{t("topup_minimum", { min: minAmountDollars })}</p>
					</div>
				</div>

				<div className="flex justify-end">
					<Button
						className="w-full sm:w-auto"
						onClick={handleSave}
						disabled={saveMutation.isPending}
					>
						{saveMutation.isPending ? (
							<>
								<Spinner size="xs" />
								{t("saving")}
							</>
						) : (
							t("save")
						)}
					</Button>
				</div>
			</section>

			<Separator />
		</div>
	);
}
