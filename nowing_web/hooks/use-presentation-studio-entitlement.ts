"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { getWorkspaceIdNumber } from "@/lib/route-params";

export const PPTX_ENTITLED_PLAN_TIERS = new Set(["team", "growth", "enterprise"]);

/**
 * Checks whether a given plan tier is entitled to generate presentations in PPTX format.
 * Paid tiers: 'team', 'growth', 'enterprise' (case-insensitive).
 * Free, unknown, or missing tiers are not entitled (Marp only).
 */
export function isPlanTierEntitledToPptx(planTier: string | null | undefined): boolean {
	if (!planTier) return false;
	return PPTX_ENTITLED_PLAN_TIERS.has(planTier.toLowerCase().trim());
}

/**
 * Rewrites presentation prompt text from PPTX references to Marp Markdown.
 * Only applied when mode is presentation_studio on a resolved free tier.
 */
export function rewritePresentationPromptToMarp(prompt: string): string {
	return prompt
		.replace(/output_format=pptx/gi, "output_format=marp")
		.replace(/as a PowerPoint PPTX file/gi, "as Marp Markdown slides")
		.replace(/dạng PowerPoint PPTX/gi, "dạng Marp Markdown")
		.replace(/PowerPoint PPTX/gi, "Marp Markdown")
		.replace(/PowerPoint/gi, "Marp")
		.replace(/\bpptx\b/gi, "marp");
}

export function usePresentationStudioEntitlement(explicitWorkspaceId?: number | null) {
	const params = useParams();
	const numericWorkspaceId =
		explicitWorkspaceId !== undefined
			? (explicitWorkspaceId ?? undefined)
			: getWorkspaceIdNumber(params);

	const {
		data: subscriptionData,
		isLoading,
		isError,
	} = useQuery({
		queryKey: cacheKeys.workspaces.subscription(numericWorkspaceId ?? 0),
		queryFn: () => workspacesApiService.getWorkspaceSubscription(numericWorkspaceId ?? 0),
		enabled: typeof numericWorkspaceId === "number" && numericWorkspaceId > 0,
	});

	// Per spec: subscription RESOLVED means subscriptionData !== undefined and not loading
	const isResolved = !isLoading && subscriptionData !== undefined;
	const planTier =
		subscriptionData?.effective_limits?.plan_tier ?? subscriptionData?.current_plan ?? null;

	const canUsePptx = isPlanTierEntitledToPptx(planTier);
	const isResolvedFreeTier = isResolved && !canUsePptx;

	return {
		workspaceId: numericWorkspaceId,
		subscriptionData,
		planTier,
		isLoading,
		isError,
		isResolved,
		canUsePptx,
		isResolvedFreeTier,
	};
}
