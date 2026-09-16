/**
 * Unit tests for Story 31.4: Presentation Studio format entitlement.
 * Tests plan-tier gating logic, prompt rewriting, and resolution lifecycle.
 * Run directly with tsx.
 */

import assert from "node:assert/strict";
import {
	isPlanTierEntitledToPptx,
	rewritePresentationPromptToMarp,
} from "../../hooks/use-presentation-studio-entitlement";

function testEntitledPlanTiers() {
	// Paid tiers are entitled (case-insensitive, trimmed)
	assert.equal(isPlanTierEntitledToPptx("team"), true);
	assert.equal(isPlanTierEntitledToPptx("growth"), true);
	assert.equal(isPlanTierEntitledToPptx("enterprise"), true);
	assert.equal(isPlanTierEntitledToPptx("TEAM"), true);
	assert.equal(isPlanTierEntitledToPptx(" Growth "), true);
	assert.equal(isPlanTierEntitledToPptx("ENTERPRISE"), true);

	// Free / unknown / missing tiers fail closed
	assert.equal(isPlanTierEntitledToPptx("free"), false);
	assert.equal(isPlanTierEntitledToPptx("FREE"), false);
	assert.equal(isPlanTierEntitledToPptx("starter"), false);
	assert.equal(isPlanTierEntitledToPptx("pro"), false);
	assert.equal(isPlanTierEntitledToPptx(""), false);
	assert.equal(isPlanTierEntitledToPptx(null), false);
	assert.equal(isPlanTierEntitledToPptx(undefined), false);
}

function testPromptRewriter() {
	const originalPrompt =
		"Create a 10-slide pitch deck as a PowerPoint PPTX file. Call generate_presentation with output_format=pptx. Cover problem, solution, market size, business model, traction, team, financials, and ask.";
	const rewritten = rewritePresentationPromptToMarp(originalPrompt);

	assert.equal(rewritten.includes("output_format=marp"), true);
	assert.equal(rewritten.includes("output_format=pptx"), false);
	assert.equal(rewritten.includes("as Marp Markdown slides"), true);
	assert.equal(rewritten.includes("as a PowerPoint PPTX file"), false);
	assert.equal(/pptx/i.test(rewritten), false);
	assert.equal(/powerpoint/i.test(rewritten), false);

	// Vietnamese translation prompt
	const vnPrompt =
		"Tạo bộ slide pitch 10 trang dạng PowerPoint PPTX. Gọi generate_presentation với output_format=pptx.";
	const vnRewritten = rewritePresentationPromptToMarp(vnPrompt);
	assert.equal(vnRewritten.includes("output_format=marp"), true);
	assert.equal(vnRewritten.includes("dạng Marp Markdown"), true);
	assert.equal(/pptx/i.test(vnRewritten), false);
}

function testResolutionLifecycleStates() {
	// Simulate the resolution state transitions used in usePresentationStudioEntitlement
	function deriveState(
		isLoading: boolean,
		subscriptionData:
			| { effective_limits?: { plan_tier?: string }; current_plan?: string }
			| undefined
	) {
		const isResolved = !isLoading && subscriptionData !== undefined;
		const planTier =
			subscriptionData?.effective_limits?.plan_tier ?? subscriptionData?.current_plan ?? null;
		const canUsePptx = isPlanTierEntitledToPptx(planTier);
		const isResolvedFreeTier = isResolved && !canUsePptx;
		return { isResolved, planTier, canUsePptx, isResolvedFreeTier };
	}

	// 1. Initial mount (loading, unresolved): MUST NOT trigger downgrade
	const loadingState = deriveState(true, undefined);
	assert.equal(loadingState.isResolved, false);
	assert.equal(loadingState.isResolvedFreeTier, false);

	// 2. Resolved with paid tier: MUST NOT trigger downgrade
	const paidState = deriveState(false, { current_plan: "team" });
	assert.equal(paidState.isResolved, true);
	assert.equal(paidState.canUsePptx, true);
	assert.equal(paidState.isResolvedFreeTier, false);

	// 3. Resolved with free tier: MUST trigger downgrade
	const freeState = deriveState(false, { current_plan: "free" });
	assert.equal(freeState.isResolved, true);
	assert.equal(freeState.canUsePptx, false);
	assert.equal(freeState.isResolvedFreeTier, true);

	// 4. Resolved with null/missing tier: fail closed to free tier
	const missingTierState = deriveState(false, {});
	assert.equal(missingTierState.isResolved, true);
	assert.equal(missingTierState.canUsePptx, false);
	assert.equal(missingTierState.isResolvedFreeTier, true);
}

testEntitledPlanTiers();
testPromptRewriter();
testResolutionLifecycleStates();
console.log("All presentation format entitlement unit checks passed.");
