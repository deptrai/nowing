"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { AlertCircle, Coins, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { instantiatePlaybookMutationAtom } from "@/atoms/playbooks/playbooks-mutation.atoms";
import { SchemaForm } from "@/components/schema-form/schema-form";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import type { PlaybookInstantiateRequest, PlaybookSummary } from "@/contracts/types/playbook.types";
import { useAutomationEligibleModels } from "@/hooks/use-automation-eligible-models";
import { playbooksApiService } from "@/lib/apis/playbooks-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import {
	AutomationModelFields,
	type AutomationModelSelection,
} from "../automations/components/builder/automation-model-fields";

interface PlaybookInstantiateDialogProps {
	playbook: PlaybookSummary;
	workspaceId: number;
	open: boolean;
	onOpenChange: (open: boolean) => void;
}

const DEFAULT_CREDIT_COST = 25;
const DEFAULT_RUN_MAX = 200;

function getRunLimitFromInputsSchema(
	inputsSchema: Record<string, unknown> | undefined,
	t: (key: any) => string
): {
	limit: number;
	label: string;
} {
	const properties =
		inputsSchema &&
		typeof inputsSchema === "object" &&
		"properties" in inputsSchema &&
		typeof inputsSchema.properties === "object" &&
		inputsSchema.properties !== null
			? (inputsSchema.properties as Record<string, unknown>)
			: undefined;
	if (!properties) {
		return { limit: DEFAULT_RUN_MAX, label: t("limit_leads") };
	}

	for (const key of ["max_leads", "max_leads_per_run", "max_skus"]) {
		const prop = properties[key];
		if (
			prop &&
			typeof prop === "object" &&
			"maximum" in prop &&
			typeof (prop as { maximum?: unknown }).maximum === "number"
		) {
			const limit = (prop as { maximum: number }).maximum;
			const label = key === "max_skus" ? "SKUs" : t("limit_leads");
			return { limit, label };
		}
	}

	return { limit: DEFAULT_RUN_MAX, label: t("limit_leads") };
}

/**
 * Opens a schema-driven form for a playbook's ``inputs.schema`` and creates an
 * automation on submit with credit estimation and INV-24.6 validation.
 */
export function PlaybookInstantiateDialog({
	playbook,
	workspaceId,
	open,
	onOpenChange,
}: PlaybookInstantiateDialogProps) {
	const t = useTranslations("playbooks");
	const router = useRouter();
	const { mutateAsync: instantiate, isPending } = useAtomValue(instantiatePlaybookMutationAtom);
	const [instantiateError, setInstantiateError] = useState<string | null>(null);
	const eligibleModels = useAutomationEligibleModels({ mode: "playbook" });
	const [modelSelection, setModelSelection] = useState<AutomationModelSelection | null>(null);

	const {
		data: detail,
		isLoading,
		error: detailError,
	} = useQuery({
		queryKey: [...cacheKeys.playbooks.detail(playbook.id)],
		queryFn: () => playbooksApiService.getPlaybook(playbook.id),
		enabled: open,
	});

	useEffect(() => {
		if (open && modelSelection === null) {
			setInstantiateError(null);
			setModelSelection({
				chatModelId: eligibleModels.llm.defaultId || 0,
				imageConfigId: eligibleModels.image.defaultId || 0,
				visionConfigId: eligibleModels.vision.defaultId || 0,
			});
		}
	}, [
		open,
		modelSelection,
		eligibleModels.llm.defaultId,
		eligibleModels.image.defaultId,
		eligibleModels.vision.defaultId,
	]);

	const resolvedModels = useMemo<AutomationModelSelection>(
		() =>
			modelSelection ?? {
				chatModelId: eligibleModels.llm.defaultId || 0,
				imageConfigId: eligibleModels.image.defaultId || 0,
				visionConfigId: eligibleModels.vision.defaultId || 0,
			},
		[
			modelSelection,
			eligibleModels.llm.defaultId,
			eligibleModels.image.defaultId,
			eligibleModels.vision.defaultId,
		]
	);

	const inputsSchema = detail?.inputs_schema as Record<string, unknown> | undefined;
	const hasInputs = !!(
		typeof inputsSchema === "object" &&
		inputsSchema !== null &&
		"properties" in inputsSchema &&
		Object.keys((inputsSchema as { properties?: Record<string, unknown> }).properties ?? {})
			.length > 0
	);

	const { limit: maxLimit, label: limitLabel } = useMemo(
		() => getRunLimitFromInputsSchema(inputsSchema, t),
		[inputsSchema, t]
	);

	const estimatedCreditsCost =
		detail?.estimated_credits_cost ?? playbook.estimated_credits_cost ?? DEFAULT_CREDIT_COST;

	async function handleSubmit(values?: Record<string, unknown>) {
		setInstantiateError(null);
		try {
			const requestPayload: PlaybookInstantiateRequest = {
				workspace_id: workspaceId,
				inputs: hasInputs ? (values ?? {}) : {},
				models: {
					chat_model_id: resolvedModels.chatModelId,
					image_gen_model_id: resolvedModels.imageConfigId,
					vision_model_id: resolvedModels.visionConfigId,
				},
			};

			const automation = await instantiate({
				playbookId: playbook.id,
				request: requestPayload,
			});
			onOpenChange(false);
			router.push(`/dashboard/${workspaceId}/automations/${automation.id}`);
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err ?? t("error_instantiate"));
			setInstantiateError(message);
		}
	}

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-h-[90vh] overflow-y-auto max-w-xl">
				<DialogHeader className="space-y-1.5 pb-2 border-b border-border/40">
					<div className="flex items-center gap-2">
						<Sparkles className="h-5 w-5 text-primary" aria-hidden="true" />
						<DialogTitle className="text-lg font-bold">
							{t("dialog_title", { name: playbook.name })}
						</DialogTitle>
					</div>
					<DialogDescription className="text-xs text-muted-foreground">
						{playbook.description ?? t("dialog_desc")}
					</DialogDescription>
				</DialogHeader>

				{/* Credit Preview Banner (AC-3) */}
				<Alert className="bg-primary/5 border-primary/20 py-2.5">
					<Coins className="h-4 w-4 text-primary" aria-hidden="true" />
					<AlertTitle className="text-xs font-semibold text-primary">
						Ước tính Chi Phí & Giới Hạn
					</AlertTitle>
					<AlertDescription className="text-[11px] text-muted-foreground">
						{t("cost_limit_desc_est")}{" "}
						<span className="font-semibold text-foreground">~{estimatedCreditsCost} Credits</span>{" "}
						{t("cost_limit_desc_per_run")}{" "}
						<span className="font-semibold text-foreground">
							{maxLimit} {limitLabel}
							{t("cost_limit_desc_per_run_suffix")}
						</span>{" "}
						(INV-24.6).
					</AlertDescription>
				</Alert>

				{!detailError && !isLoading && (
					<div className="space-y-2 pt-1 border-t border-border/40">
						<AutomationModelFields
							mode="playbook"
							workspaceId={workspaceId}
							value={resolvedModels}
							onChange={(patch) =>
								setModelSelection((prev) => ({
									...(prev ?? resolvedModels),
									...patch,
								}))
							}
						/>
					</div>
				)}

				{detailError ? (
					<div className="space-y-4 pt-2">
						<Alert variant="destructive">
							<AlertCircle className="h-4 w-4" aria-hidden="true" />
							<AlertTitle className="text-xs font-semibold">{t("error_detail_title")}</AlertTitle>
							<AlertDescription className="text-[11px]">
								{detailError.message || t("error_detail_desc")}
							</AlertDescription>
						</Alert>
						<DialogFooter>
							<Button type="button" variant="outline" size="sm" onClick={() => onOpenChange(false)}>
								Hủy bỏ
							</Button>
						</DialogFooter>
					</div>
				) : isLoading ? (
					<div className="flex justify-center py-12">
						<Spinner className="h-7 w-7 text-primary" />
					</div>
				) : hasInputs && inputsSchema ? (
					<div className="pt-2">
						<SchemaForm
							// biome-ignore lint/suspicious/noExplicitAny: JSON Schema is dynamic.
							schema={inputsSchema as any}
							onSubmit={handleSubmit}
							submitLabel={isPending ? t("instantiating") : t("submit_btn")}
							disabled={isPending}
						/>

						{instantiateError && (
							<p className="text-xs text-destructive pt-2 font-medium">{instantiateError}</p>
						)}
					</div>
				) : (
					<div className="space-y-4 pt-2">
						{instantiateError && <p className="text-xs text-destructive">{instantiateError}</p>}
						<DialogFooter>
							<Button type="button" variant="outline" size="sm" onClick={() => onOpenChange(false)}>
								Hủy bỏ
							</Button>
							<Button type="button" size="sm" onClick={() => handleSubmit()} disabled={isPending}>
								{isPending ? t("instantiating") : t("run_now_btn")}
							</Button>
						</DialogFooter>
					</div>
				)}
			</DialogContent>
		</Dialog>
	);
}
