"use client";

import { useAui, useAuiState } from "@assistant-ui/react";
import { useCallback, useRef, useState } from "react";
import type { SuggestedAction } from "@/contracts/types/chat-messages.types";

export interface UseSuggestedActionDispatchOptions {
	/** Optional callback invoked before dispatching */
	onBeforeDispatch?: (action: SuggestedAction) => void;
	/** Optional custom dispatch handler if overriding default AUI append */
	customHandler?: (action: SuggestedAction) => Promise<void> | void;
}

export function useSuggestedActionDispatch(options?: UseSuggestedActionDispatchOptions) {
	const [isDispatching, setIsDispatching] = useState(false);
	const isDispatchingRef = useRef(false);
	const aui = useAui();
	const isRunning = useAuiState((s) => s.thread?.isRunning ?? false);

	const dispatchAction = useCallback(
		async (action: SuggestedAction) => {
			if (!action || isDispatchingRef.current || isRunning) return;

			const thread = aui.thread();
			isDispatchingRef.current = true;
			setIsDispatching(true);
			options?.onBeforeDispatch?.(action);

			try {
				if (options?.customHandler) {
					await options.customHandler(action);
				} else if (thread?.append) {
					// Default: Append prompt into active Assistant-UI thread session
					await thread.append({
						role: "user",
						content: [{ type: "text", text: action.prompt_template }],
					});
				}

				// Trigger Zero-cache mutation pulse highlight event across window
				if (typeof window !== "undefined") {
					window.dispatchEvent(
						new CustomEvent("nowing:action-dispatched", {
							detail: {
								action_type: action.action_type,
								payload: action.payload ?? {},
								timestamp: Date.now(),
							},
						})
					);
				}
			} catch (err) {
				console.error("[useSuggestedActionDispatch] Failed to dispatch action:", err);
			} finally {
				isDispatchingRef.current = false;
				setIsDispatching(false);
			}
		},
		[aui, options, isRunning]
	);

	return {
		dispatchAction,
		isDispatching,
	};
}
