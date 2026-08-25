"use client";

import type { MarkToolRect } from "@/contracts/types/web-builder.types";

interface MarkToolOverlayProps {
	selectedSelector: string;
	patchText: string;
	patchType: "text" | "className" | "style" | "attribute" | "replace";
	attributeName: string;
	componentHint?: string;
	rect?: MarkToolRect;
	isPending: boolean;
	onSelectorChange: (value: string) => void;
	onPatchTextChange: (value: string) => void;
	onPatchTypeChange: (value: "text" | "className" | "style" | "attribute" | "replace") => void;
	onAttributeNameChange: (value: string) => void;
	onApply: () => void;
}

export function MarkToolOverlay({
	selectedSelector,
	patchText,
	patchType,
	attributeName,
	componentHint,
	rect,
	isPending,
	onSelectorChange,
	onPatchTextChange,
	onPatchTypeChange,
	onAttributeNameChange,
	onApply,
}: MarkToolOverlayProps) {
	return (
		<div className="p-3 bg-indigo-50/20 dark:bg-indigo-950/30 border-b border-indigo-500/30 flex flex-col gap-2">
			<div className="flex items-center gap-3">
				<input
					type="text"
					placeholder="DOM Selector (e.g. #hero-title or h1) — Click element in preview to select"
					value={selectedSelector}
					onChange={(e) => onSelectorChange(e.target.value)}
					className="text-xs px-2.5 py-1.5 rounded border border-border bg-background flex-1 focus:ring-1 focus:ring-indigo-500"
				/>
				<select
					value={patchType}
					onChange={(e) =>
						onPatchTypeChange(
							e.target.value as "text" | "className" | "style" | "attribute" | "replace"
						)
					}
					className="text-xs px-2 py-1.5 rounded border border-border bg-background focus:ring-1 focus:ring-indigo-500"
					title="Patch type"
				>
					<option value="text">Text</option>
					<option value="className">Class</option>
					<option value="style">Style</option>
					<option value="attribute">Attribute</option>
					<option value="replace">Replace</option>
				</select>
			</div>
			<div className="flex items-center gap-3">
				{patchType === "attribute" && (
					<input
						type="text"
						placeholder="Attribute name (e.g. data-label)"
						value={attributeName}
						onChange={(e) => onAttributeNameChange(e.target.value)}
						className="text-xs px-2.5 py-1.5 rounded border border-border bg-background w-40 focus:ring-1 focus:ring-indigo-500"
					/>
				)}
				<input
					type="text"
					placeholder={
						patchType === "replace"
							? "New JSX snippet..."
							: patchType === "attribute"
								? "New attribute value..."
								: "New value..."
					}
					value={patchText}
					onChange={(e) => onPatchTextChange(e.target.value)}
					className="text-xs px-2.5 py-1.5 rounded border border-border bg-background flex-1 focus:ring-1 focus:ring-indigo-500"
				/>
				<button
					type="button"
					onClick={onApply}
					disabled={
						isPending || !selectedSelector || (patchType === "attribute" && !attributeName.trim())
					}
					className="px-3 py-1.5 text-xs font-medium bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50 transition-colors"
				>
					{isPending ? "Patching..." : "Apply Patch"}
				</button>
			</div>
			{(componentHint || rect) && (
				<div className="flex items-center gap-3 text-[10px] text-muted-foreground">
					{componentHint && <span>Hint: {componentHint}</span>}
					{rect && (
						<span>
							rect: {Math.round(rect.x)},{Math.round(rect.y)} {Math.round(rect.width)}x
							{Math.round(rect.height)}
						</span>
					)}
				</div>
			)}
		</div>
	);
}
