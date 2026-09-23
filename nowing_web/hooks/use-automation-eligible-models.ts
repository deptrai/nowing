"use client";

import { useAtomValue } from "jotai";
import { useMemo } from "react";
import {
	globalModelConnectionsAtom,
	modelConnectionsAtom,
	modelRolesAtom,
} from "@/atoms/model-connections/model-connections-query.atoms";
import type { ConnectionRead, ModelRead } from "@/contracts/types/model-connections.types";

/**
 * A single model the user may pick for an automation slot.
 */
export interface EligibleModelOption {
	id: number;
	name: string;
	/** Underlying model identifier (e.g. `gpt-4o`); shown as secondary text. */
	modelName: string;
	provider: string;
	/** `true` for user BYOK configs (positive ids), `false` for global models. */
	isBYOK: boolean;
	tier?: "free" | "premium" | "byok";
}

export interface EligibleModelKind {
	options: EligibleModelOption[];
	/** Default selection: the workspace pref when eligible, else first option. */
	defaultId: number | null;
	/** O(1) id → option lookup for trigger labels (avoids per-render `.find()`). */
	byId: Map<number, EligibleModelOption>;
}

export interface AutomationEligibleModels {
	llm: EligibleModelKind;
	image: EligibleModelKind;
	vision: EligibleModelKind;
	isLoading: boolean;
}

export interface UseAutomationEligibleModelsOptions {
	allowFreeGlobals?: boolean;
	mode?: "automation" | "playbook";
}

/**
 * Build the eligible option list for one model kind: premium/all globals
 * followed by all BYOK/workspace models.
 */
function buildKind(
	globals: ConnectionRead[] | undefined,
	byok: ConnectionRead[] | undefined,
	capability: "chat" | "image_gen" | "vision",
	prefId: number | null | undefined,
	allowFreeGlobals = false
): EligibleModelKind {
	const supportsCapability = (model: ModelRead) => {
		if (capability === "chat") return Boolean(model.supports_chat);
		if (capability === "vision") return Boolean(model.supports_image_input);
		return Boolean(model.supports_image_generation);
	};
	const toOption = (
		connection: ConnectionRead,
		model: ModelRead,
		isBYOK: boolean
	): EligibleModelOption => {
		const billingTier = String(model.billing_tier ?? "").toLowerCase();
		const tier: "free" | "premium" | "byok" = isBYOK
			? "byok"
			: billingTier === "premium"
				? "premium"
				: "free";
		return {
			id: model.id,
			name: model.display_name || model.model_id,
			modelName: model.model_id,
			provider: connection.provider,
			isBYOK,
			tier,
		};
	};

	const globalOptions: EligibleModelOption[] = (globals ?? []).flatMap((connection) =>
		connection.models
			.filter((model) => {
				if (!model.enabled || !supportsCapability(model)) return false;
				if (allowFreeGlobals) return true;
				return String(model.billing_tier ?? "").toLowerCase() === "premium";
			})
			.map((model) => toOption(connection, model, false))
	);

	const byokOptions: EligibleModelOption[] = (byok ?? []).flatMap((connection) =>
		connection.models
			.filter((model) => model.enabled && supportsCapability(model))
			.map((model) => toOption(connection, model, true))
	);

	const options = [...globalOptions, ...byokOptions];
	const byId = new Map<number, EligibleModelOption>(options.map((o) => [o.id, o]));

	let defaultId: number | null = null;
	if (prefId != null && byId.has(prefId)) {
		defaultId = prefId;
	} else if (options.length > 0) {
		defaultId = options[0].id;
	}

	return { options, defaultId, byId };
}

/**
 * Lists the LLM / image / vision models that are eligible for automations
 * (premium globals + user BYOK by default, or all globals when allowFreeGlobals / playbook mode),
 * with a default selection seeded from the workspace's role preferences.
 *
 * Everything is derived during render from the connection/model query atoms;
 * there are no effects, so option lists/maps keep stable references.
 */
export function useAutomationEligibleModels(
	options?: UseAutomationEligibleModelsOptions
): AutomationEligibleModels {
	const { data: byokConnections, isLoading: byokLoading } = useAtomValue(modelConnectionsAtom);
	const { data: globalConnections, isLoading: globalLoading } = useAtomValue(
		globalModelConnectionsAtom
	);
	const { data: roles, isLoading: rolesLoading } = useAtomValue(modelRolesAtom);

	const allowFreeGlobals = Boolean(options?.allowFreeGlobals || options?.mode === "playbook");

	const llm = useMemo(
		() =>
			buildKind(globalConnections, byokConnections, "chat", roles?.chat_model_id, allowFreeGlobals),
		[globalConnections, byokConnections, roles?.chat_model_id, allowFreeGlobals]
	);

	const image = useMemo(
		() =>
			buildKind(
				globalConnections,
				byokConnections,
				"image_gen",
				roles?.image_gen_model_id,
				allowFreeGlobals
			),
		[globalConnections, byokConnections, roles?.image_gen_model_id, allowFreeGlobals]
	);

	const vision = useMemo(
		() =>
			buildKind(
				globalConnections,
				byokConnections,
				"vision",
				roles?.vision_model_id,
				allowFreeGlobals
			),
		[globalConnections, byokConnections, roles?.vision_model_id, allowFreeGlobals]
	);

	const isLoading = byokLoading || globalLoading || rolesLoading;

	return useMemo(() => ({ llm, image, vision, isLoading }), [llm, image, vision, isLoading]);
}
