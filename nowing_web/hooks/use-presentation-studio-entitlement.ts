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
 * Deliberately does NOT touch a ".pptx" file extension — Marp emits Markdown,
 * not a .marp file, so a literal filename like `deck.pptx` is left alone.
 */
export function rewritePresentationPromptToMarp(prompt: string): string {
	return (
		prompt
			.replace(/output_format\s*=\s*pptx/gi, "output_format=marp")
			.replace(/\/slides\s+pptx\b/gi, "/slides marp")
			.replace(/as a PowerPoint PPTX file/gi, "as Marp Markdown slides")
			.replace(/dạng PowerPoint PPTX/gi, "dạng Marp Markdown")
			.replace(/PowerPoint PPTX/gi, "Marp Markdown")
			.replace(/PowerPoint/gi, "Marp")
			// (?<!\.) guards a real ".pptx" file extension; the trailing lookahead
			// (?![a-zA-Z0-9]) (instead of (?!\.)) lets sentence-final "pptx." still
			// be rewritten while "file.pptx" stays intact.
			.replace(/(?<!\.)\bpptx\b(?![a-zA-Z0-9])/gi, "marp")
	);
}

/** Entitlement payload shape returned by the member-readable endpoint. */
export interface WorkspaceEntitlementLike {
	plan_tier: string;
	can_use_pptx: boolean;
	self_hosted?: boolean;
}

/**
 * Pure derivation of the resolution lifecycle from a subscription query.
 * Exported (and unit-tested) so a regression in `isResolvedFreeTier` /
 * `canUsePptx` is caught by tests rather than only surfacing in the UI.
 */
export function deriveEntitlementState(
	isLoading: boolean,
	entitlementData: WorkspaceEntitlementLike | undefined
) {
	// Per spec: subscription RESOLVED means data !== undefined and not loading.
	const isResolved = !isLoading && entitlementData !== undefined;
	const planTier = entitlementData?.plan_tier ?? null;
	// Explicitly self-hosted deployments have unlimited licensing — always
	// entitled to PPTX regardless of the workspace's stored plan tier.
	const canUsePptx =
		entitlementData?.self_hosted === true ||
		(entitlementData?.can_use_pptx ?? isPlanTierEntitledToPptx(planTier));
	const isResolvedFreeTier = isResolved && !canUsePptx;
	return { isResolved, planTier, canUsePptx, isResolvedFreeTier };
}

/**
 * Decide whether a presentation_studio URL should be downgraded to Marp.
 * Pure & exported so the page-level effect is unit-testable without a DOM.
 * Returns the new format+prompt to write back, or null when nothing changes.
 */
export function computeStudioDowngrade(
	isPresentationStudioMode: boolean,
	isResolvedFreeTier: boolean,
	formatParam: string | null,
	rawPrompt: string | null
): { format?: string; prompt?: string } | null {
	if (!isPresentationStudioMode || !isResolvedFreeTier) return null;
	const out: { format?: string; prompt?: string } = {};
	if (formatParam && formatParam.toLowerCase() === "pptx") out.format = "marp";
	if (rawPrompt) {
		const rewritten = rewritePresentationPromptToMarp(rawPrompt);
		if (rewritten !== rawPrompt) out.prompt = rewritten;
	}
	return Object.keys(out).length ? out : null;
}

export function usePresentationStudioEntitlement(explicitWorkspaceId?: number | null) {
	const params = useParams();
	const numericWorkspaceId =
		explicitWorkspaceId !== undefined
			? (explicitWorkspaceId ?? undefined)
			: getWorkspaceIdNumber(params);

	const {
		data: entitlementData,
		isLoading,
		isError,
	} = useQuery({
		queryKey: cacheKeys.workspaces.entitlement(numericWorkspaceId ?? 0),
		// Member-readable endpoint (no SETTINGS_VIEW) so non-admin members on a
		// paid workspace still resolve their PPTX entitlement correctly.
		queryFn: () => workspacesApiService.getWorkspaceEntitlement(numericWorkspaceId ?? 0),
		enabled: typeof numericWorkspaceId === "number" && numericWorkspaceId > 0,
	});

	const { isResolved, planTier, canUsePptx, isResolvedFreeTier } = deriveEntitlementState(
		isLoading,
		entitlementData
	);

	return {
		workspaceId: numericWorkspaceId,
		subscriptionData: entitlementData,
		planTier,
		isLoading,
		isError,
		isResolved,
		canUsePptx,
		isResolvedFreeTier,
	};
}
