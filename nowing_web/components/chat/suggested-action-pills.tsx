"use client";

import { Download, type LucideIcon, MessageSquare, Phone, Search, Sparkles } from "lucide-react";
import type React from "react";
import { useCallback, useEffect } from "react";
import type { SuggestedAction } from "@/contracts/types/chat-messages.types";
import { useSuggestedActionDispatch } from "@/lib/hooks/use-suggested-action-dispatch";
import { cn } from "@/lib/utils";

export interface SuggestedActionPillsProps {
	/** List of suggested actions emitted with the assistant message (max 3) */
	actions: SuggestedAction[];
	/** Whether this is the active/last assistant turn where keyboard shortcuts apply */
	isLast?: boolean;
	/** Whether interactions are disabled (e.g. streaming active) */
	disabled?: boolean;
	/** Optional callback when an action is selected */
	onSelectAction?: (action: SuggestedAction) => void;
	/** Optional custom container CSS classes */
	className?: string;
}

const ICON_MAP: Record<string, LucideIcon> = {
	phone: Phone,
	"message-square": MessageSquare,
	search: Search,
	download: Download,
	sparkles: Sparkles,
};

export const SuggestedActionPills: React.FC<SuggestedActionPillsProps> = ({
	actions,
	isLast = true,
	disabled = false,
	onSelectAction,
	className,
}) => {
	const { dispatchAction, isDispatching } = useSuggestedActionDispatch();

	const displayedActions = actions.slice(0, 3);

	const handleActionClick = useCallback(
		(action: SuggestedAction) => {
			if (disabled || isDispatching) return;
			if (onSelectAction) {
				onSelectAction(action);
			} else {
				dispatchAction(action);
			}
		},
		[disabled, isDispatching, onSelectAction, dispatchAction]
	);

	// Register keyboard shortcuts (Alt+1, Alt+2, Alt+3) on active last turn
	useEffect(() => {
		if (!isLast || disabled || isDispatching || displayedActions.length === 0) {
			return;
		}

		const handleKeyDown = (e: KeyboardEvent) => {
			// Ignore if not Alt or if combined with other modifiers
			if (!e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;

			// Ignore if user is typing in a form input, textarea, editor or modal
			const target = e.target as HTMLElement | null;
			if (
				target &&
				(target.tagName === "INPUT" ||
					target.tagName === "TEXTAREA" ||
					target.isContentEditable ||
					target.closest("[role='dialog']"))
			) {
				return;
			}

			let index = -1;
			if (e.key === "1" || e.code === "Digit1") index = 0;
			else if (e.key === "2" || e.code === "Digit2") index = 1;
			else if (e.key === "3" || e.code === "Digit3") index = 2;

			if (index >= 0 && index < displayedActions.length) {
				e.preventDefault();
				handleActionClick(displayedActions[index]);
			}
		};

		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, [isLast, disabled, isDispatching, displayedActions, handleActionClick]);

	if (!displayedActions || displayedActions.length === 0) {
		return null;
	}

	return (
		<div
			className={cn(
				"aui-suggested-actions-container mt-2.5 flex flex-wrap items-center gap-2",
				className
			)}
			data-testid="suggested-action-pills"
		>
			{displayedActions.map((action, index) => {
				const IconComponent = ICON_MAP[action.icon] ?? Sparkles;
				const shortcutIndex = index + 1;

				return (
					<button
						key={action.id || `action-${index}`}
						type="button"
						onClick={() => handleActionClick(action)}
						disabled={disabled || isDispatching}
						className={cn(
							"group inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-all duration-150 select-none",
							"bg-emerald-50 text-emerald-900 border border-emerald-200 hover:bg-emerald-100 hover:border-emerald-300 shadow-xs",
							"dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/60 dark:hover:bg-emerald-900/50 dark:hover:border-emerald-700",
							"focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50",
							(disabled || isDispatching) && "opacity-50 cursor-not-allowed pointer-events-none"
						)}
						title={action.label}
						data-testid={`suggested-action-pill-${index}`}
						data-action-type={action.action_type}
					>
						<IconComponent
							className="size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400 group-hover:scale-110 transition-transform"
							aria-hidden="true"
						/>
						<span className="truncate max-w-[280px]">{action.label}</span>
						{isLast && (
							<kbd className="ml-1 rounded px-1 py-0.5 text-[9px] font-mono text-emerald-700/70 dark:text-emerald-400/60 border border-emerald-300/50 dark:border-emerald-800/60 bg-emerald-100/50 dark:bg-emerald-900/30">
								⌥{shortcutIndex}
							</kbd>
						)}
					</button>
				);
			})}
		</div>
	);
};
