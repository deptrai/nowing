"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { Bell, BookmarkPlus, FlaskConical, GitCompareArrows, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
	addToWatchlistAtom,
	isInWatchlistAtom,
	removeFromWatchlistAtom,
	watchlistAtom,
} from "@/lib/crypto/watchlist-atom";
import { createPriceAlertAtom } from "@/lib/crypto/price-alert-atom";
import { pendingDeepDiveAtom } from "@/lib/crypto/deep-dive-atom";
import { cn } from "@/lib/utils";

const WATCHLIST_CAP = 50;

interface NextActionBarProps {
	tokenSymbol?: string;
	tokenName?: string;
	onOpenCompare?: () => void;
	onOpenScenario?: () => void;
	className?: string;
}

function isEditableTarget(target: EventTarget | null): boolean {
	if (!(target instanceof HTMLElement)) return false;
	const tag = target.tagName;
	return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

/**
 * CSS-only modal — avoids @radix-ui/react-presence which crashes with React 19
 * when setState is called from a ref callback inside React's commit phase.
 */
function CreateAlertDialog({
	open,
	onClose,
	tokenSymbol,
	tokenName,
}: {
	open: boolean;
	onClose: () => void;
	tokenSymbol: string;
	tokenName: string;
}) {
	const [threshold, setThreshold] = useState("");
	const [direction, setDirection] = useState<"above" | "below">("above");
	const createAlert = useSetAtom(createPriceAlertAtom);
	const inputRef = useRef<HTMLInputElement>(null);
	const [mounted, setMounted] = useState(false);

	useEffect(() => {
		setMounted(true);
	}, []);

	// Focus input when opened
	useEffect(() => {
		if (open) {
			const t = setTimeout(() => inputRef.current?.focus(), 50);
			return () => clearTimeout(t);
		}
	}, [open]);

	// Escape to close
	useEffect(() => {
		if (!open) return;
		const handleKey = (e: KeyboardEvent) => {
			if (e.key === "Escape") onClose();
		};
		document.addEventListener("keydown", handleKey);
		return () => document.removeEventListener("keydown", handleKey);
	}, [open, onClose]);

	const parsedThreshold = parseFloat(threshold);
	const isThresholdValid = Number.isFinite(parsedThreshold) && parsedThreshold > 0;

	const handleSubmit = useCallback(() => {
		if (!isThresholdValid) return;
		createAlert({
			symbol: tokenSymbol,
			name: tokenName,
			threshold: parsedThreshold,
			direction,
		});
		toast.success(
			`Alert saved: ${tokenSymbol} ${direction === "above" ? ">" : "<"} $${parsedThreshold}`,
			{ description: "Local only — alerts are not monitored yet" }
		);
		onClose();
		setThreshold("");
	}, [isThresholdValid, parsedThreshold, direction, tokenSymbol, tokenName, createAlert, onClose]);

	if (!mounted || !open) return null;

	return createPortal(
		<>
			{/* Backdrop */}
			<div
				className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm animate-in fade-in duration-150"
				onClick={onClose}
				aria-hidden="true"
			/>
			{/* Modal */}
			<div
				role="dialog"
				aria-modal="true"
				aria-labelledby="price-alert-title"
				className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-full max-w-xs bg-background rounded-xl border shadow-2xl p-6 animate-in fade-in zoom-in-95 duration-150"
			>
				{/* Close button */}
				<button
					type="button"
					onClick={onClose}
					className="absolute right-4 top-4 h-8 w-8 rounded-full inline-flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
					aria-label="Close"
				>
					<X className="h-4 w-4" />
				</button>

				{/* Title */}
				<h2 id="price-alert-title" className="text-lg font-semibold mb-4">
					Price Alert — {tokenSymbol}
				</h2>

				{/* Body */}
				<div className="flex flex-col gap-3">
					<div className="flex gap-2">
						<Button
							size="sm"
							variant={direction === "above" ? "default" : "outline"}
							onClick={() => setDirection("above")}
							className="flex-1"
						>
							Above
						</Button>
						<Button
							size="sm"
							variant={direction === "below" ? "default" : "outline"}
							onClick={() => setDirection("below")}
							className="flex-1"
						>
							Below
						</Button>
					</div>
					<Input
						ref={inputRef}
						type="number"
						placeholder="e.g. 0.50"
						value={threshold}
						onChange={(e) => setThreshold(e.target.value)}
						onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
					/>
				</div>

				{/* Footer */}
				<div className="flex justify-end gap-2 mt-4">
					<Button variant="outline" size="sm" onClick={onClose}>
						Cancel
					</Button>
					<Button size="sm" onClick={handleSubmit} disabled={!isThresholdValid}>
						Set Alert
					</Button>
				</div>
			</div>
		</>,
		document.body
	);
}

export function NextActionBar({
	tokenSymbol = "TOKEN",
	tokenName = "",
	onOpenCompare,
	onOpenScenario: _onOpenScenario,
	className,
}: NextActionBarProps) {
	const setPendingDeepDive = useSetAtom(pendingDeepDiveAtom);
	const addToWatchlist = useSetAtom(addToWatchlistAtom);
	const removeFromWatchlist = useSetAtom(removeFromWatchlistAtom);
	const watchlist = useAtomValue(watchlistAtom);
	const inWatchlist = useAtomValue(isInWatchlistAtom(tokenSymbol));
	const [alertOpen, setAlertOpen] = useState(false);

	const handleWatchlist = useCallback(() => {
		if (inWatchlist) {
			toast.info(`${tokenSymbol} is already in your watchlist`);
			return;
		}
		// Warn before silent eviction at cap
		if (watchlist.length >= WATCHLIST_CAP) {
			toast.warning(
				`Watchlist is full (${WATCHLIST_CAP} tokens). Remove some tokens before adding new ones.`
			);
			return;
		}
		addToWatchlist({ symbol: tokenSymbol, name: tokenName });
		toast.success(`${tokenSymbol} added to watchlist`, {
			action: {
				label: "Undo",
				onClick: () => removeFromWatchlist(tokenSymbol),
			},
		});
	}, [inWatchlist, watchlist.length, tokenSymbol, tokenName, addToWatchlist, removeFromWatchlist]);

	const handleDeepDive = useCallback(() => {
		const prompt = `Deep analysis of ${tokenName || tokenSymbol}: `;
		setPendingDeepDive(prompt);
		toast.info("Deep dive prompt ready — edit and submit when ready");
	}, [setPendingDeepDive, tokenSymbol, tokenName]);

	// Keyboard shortcuts (⌘⇧ variants to avoid browser conflicts)
	useEffect(() => {
		const handleKey = (e: KeyboardEvent) => {
			if (!e.metaKey && !e.ctrlKey) return;
			if (!e.shiftKey) return;
			// Skip when user is typing in an input/textarea/contenteditable
			if (isEditableTarget(e.target)) return;
			switch (e.key.toLowerCase()) {
				case "w":
					e.preventDefault();
					handleWatchlist();
					break;
				case "a":
					e.preventDefault();
					queueMicrotask(() => setAlertOpen(true));
					break;
				case "k":
					e.preventDefault();
					onOpenCompare?.();
					break;
				case "d":
					e.preventDefault();
					handleDeepDive();
					break;
			}
		};
		window.addEventListener("keydown", handleKey);
		return () => window.removeEventListener("keydown", handleKey);
	}, [handleWatchlist, handleDeepDive, onOpenCompare]);

	const actions = [
		{
			icon: BookmarkPlus,
			title: "Watchlist",
			description: inWatchlist ? `${tokenSymbol} in watchlist` : `Add ${tokenSymbol}`,
			shortcut: "⌘⇧W",
			onClick: handleWatchlist,
			active: inWatchlist,
		},
		{
			icon: Bell,
			title: "Price Alert",
			description: `Save price alert (local only)`,
			shortcut: "⌘⇧A",
			onClick: () => queueMicrotask(() => setAlertOpen(true)),
		},
		{
			icon: GitCompareArrows,
			title: "Compare",
			description: `Compare ${tokenSymbol} vs...`,
			shortcut: "⌘⇧K",
			onClick: () => onOpenCompare?.(),
		},
		{
			icon: FlaskConical,
			title: "Deep Dive",
			description: `Deep dive ${tokenSymbol}`,
			shortcut: "⌘⇧D",
			onClick: handleDeepDive,
		},
	];

	return (
		<>
			<div
				className={cn(
					"mt-8 grid grid-cols-1 sm:grid-cols-2 gap-3 rounded-2xl border bg-muted/30 p-4",
					className
				)}
				data-slot="next-action-bar"
			>
				{actions.map((action) => (
					<button
						key={action.title}
						onClick={action.onClick}
						className={cn(
							"flex flex-col gap-1.5 rounded-xl border bg-background p-3 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
							action.active && "border-primary/30 bg-primary/5"
						)}
					>
						<div className="flex items-center justify-between">
							<action.icon className="size-4 text-muted-foreground" />
							<span className="text-[10px] text-muted-foreground font-mono">{action.shortcut}</span>
						</div>
						<div>
							<p className="text-sm font-medium leading-none">{action.title}</p>
							<p className="mt-1 text-xs text-muted-foreground line-clamp-1">
								{action.description}
							</p>
						</div>
					</button>
				))}
			</div>
			<CreateAlertDialog
				open={alertOpen}
				onClose={() => setAlertOpen(false)}
				tokenSymbol={tokenSymbol}
				tokenName={tokenName}
			/>
		</>
	);
}
