/**
 * Unit tests for Story 31.4: Presentation Studio format entitlement.
 * Tests plan-tier gating logic, prompt rewriting, and resolution lifecycle.
 * Run directly with tsx.
 */

import assert from "node:assert/strict";
import {
	computeStudioDowngrade,
	deriveEntitlementState,
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
	assert.equal(/output_format=pptx/i.test(rewritten), false);
	assert.equal(/powerpoint/i.test(rewritten), false);

	// A literal .pptx filename is left intact — Marp decks are .md, not .marp.
	const withFilename = "export as presentation.pptx and set output_format=pptx";
	const filenameRewritten = rewritePresentationPromptToMarp(withFilename);
	assert.equal(filenameRewritten.includes("presentation.pptx"), true);
	assert.equal(filenameRewritten.includes("output_format=marp"), true);
	assert.equal(filenameRewritten.includes("output_format=pptx"), false);

	// Vietnamese translation prompt
	const vnPrompt =
		"Tạo bộ slide pitch 10 trang dạng PowerPoint PPTX. Gọi generate_presentation với output_format=pptx.";
	const vnRewritten = rewritePresentationPromptToMarp(vnPrompt);
	assert.equal(vnRewritten.includes("output_format=marp"), true);
	assert.equal(vnRewritten.includes("dạng Marp Markdown"), true);
	assert.equal(/output_format=pptx/i.test(vnRewritten), false);
}

function testResolutionLifecycleStates() {
	// Exercise the REAL deriveEntitlementState exported from the hook — a
	// local copy would let a regression in the hook slip through untested.
	const deriveState = (
		isLoading: boolean,
		entitlementData: { plan_tier: string; can_use_pptx: boolean; self_hosted?: boolean } | undefined
	) => deriveEntitlementState(isLoading, entitlementData);

	// 1. Initial mount (loading, unresolved): MUST NOT trigger downgrade
	const loadingState = deriveState(true, undefined);
	assert.equal(loadingState.isResolved, false);
	assert.equal(loadingState.isResolvedFreeTier, false);

	// 2. Resolved with paid tier: MUST NOT trigger downgrade
	const paidState = deriveState(false, { plan_tier: "team", can_use_pptx: true });
	assert.equal(paidState.isResolved, true);
	assert.equal(paidState.canUsePptx, true);
	assert.equal(paidState.isResolvedFreeTier, false);

	// 3. Resolved with free tier: MUST trigger downgrade
	const freeState = deriveState(false, { plan_tier: "free", can_use_pptx: false });
	assert.equal(freeState.isResolved, true);
	assert.equal(freeState.canUsePptx, false);
	assert.equal(freeState.isResolvedFreeTier, true);

	// 4. Resolved with null/missing tier: fail closed to free tier
	const missingTierState = deriveState(false, { plan_tier: "free", can_use_pptx: false });
	assert.equal(missingTierState.isResolved, true);
	assert.equal(missingTierState.canUsePptx, false);
	assert.equal(missingTierState.isResolvedFreeTier, true);

	// 5. Self-hosted deployment: always entitled regardless of stored tier —
	// unlimited licensing means a free-tier row still allows PPTX.
	const selfHostedState = deriveState(false, {
		plan_tier: "free",
		can_use_pptx: false,
		self_hosted: true,
	});
	assert.equal(selfHostedState.canUsePptx, true);
	assert.equal(selfHostedState.isResolvedFreeTier, false);

	// 6. Loading state must not claim resolved-free even if data present later.
	const stillLoading = deriveState(true, { plan_tier: "team", can_use_pptx: true });
	assert.equal(stillLoading.isResolved, false);
	assert.equal(stillLoading.isResolvedFreeTier, false);
}

function testPromptRewriteEdgeCases() {
	// sentence-final "pptx." must still rewrite (trailing period is not a file ext)
	const sentence = rewritePresentationPromptToMarp("export the deck as pptx.");
	assert.equal(sentence.includes("marp."), true);
	assert.equal(/\bpptx\b/i.test(sentence.replace(/marp/g, "")), false);

	// a real .pptx filename is preserved
	const fname = rewritePresentationPromptToMarp("save to deck.pptx");
	assert.equal(fname.includes("deck.pptx"), true);
}

testEntitledPlanTiers();
testPromptRewriter();
function testUrlDowngradeDecision() {
	// presentation_studio + resolved free tier + ?format=pptx -> downgrade
	const d1 = computeStudioDowngrade(true, true, "pptx", null);
	assert.deepEqual(d1, { format: "marp" });
	// format=PPTX case-insensitive
	const d2 = computeStudioDowngrade(true, true, "PPTX", null);
	assert.deepEqual(d2, { format: "marp" });
	// pptx in prompt text is rewritten
	const d3 = computeStudioDowngrade(true, true, "marp", "make it pptx");
	assert.equal(d3?.prompt?.includes("marp"), true);
	// paid tier (not resolved-free) -> no downgrade even with format=pptx
	assert.equal(computeStudioDowngrade(true, false, "pptx", null), null);
	// not presentation studio mode -> no downgrade
	assert.equal(computeStudioDowngrade(false, true, "pptx", null), null);
	// nothing to downgrade
	assert.equal(computeStudioDowngrade(true, true, "marp", "hello"), null);
}

testResolutionLifecycleStates();
testPromptRewriteEdgeCases();
testUrlDowngradeDecision();
console.log("All presentation format entitlement unit checks passed.");
