"use client";

import { useAtom, useSetAtom } from "jotai";
import { ChevronDown, ChevronRight, Table as TableIcon } from "lucide-react";
import type React from "react";
import { useState } from "react";
import {
	activeArtifactIdAtom,
	canvasHighlightTriggerAtom,
	canvasModeAtom,
	threadCanvasModeMapAtom,
} from "@/atoms/leads/leads-canvas.atoms";
import { cn } from "@/lib/utils";

export interface TableArtifactCardProps {
	id?: string;
	title?: string;
	rowCount?: number;
	type?: "TABLE" | "LEADS" | "PLAN" | "REPORT";
	children?: React.ReactNode; // Optional raw table for inline accordion toggle
	threadId?: string | number | null;
	className?: string;
}

export const TableArtifactCard: React.FC<TableArtifactCardProps> = ({
	id = "leads-matrix-main",
	title = "Danh sách Khách hàng Tiềm năng",
	rowCount,
	type = "TABLE",
	children,
	threadId,
	className,
}) => {
	const [activeArtifactId, setActiveArtifactId] = useAtom(activeArtifactIdAtom);
	const setCanvasHighlight = useSetAtom(canvasHighlightTriggerAtom);
	const [, setThreadModesMap] = useAtom(threadCanvasModeMapAtom);
	const setGlobalCanvasMode = useSetAtom(canvasModeAtom);

	const [isInlineExpanded, setIsInlineExpanded] = useState(false);

	const isActive = activeArtifactId === id;

	const handlePingRightPanel = (e: React.MouseEvent) => {
		e.stopPropagation();
		setActiveArtifactId(id);

		// Switch Right Canvas mode to leads
		const threadKey = String(threadId || "default");
		setThreadModesMap((prev) => ({
			...prev,
			[threadKey]: "leads",
		}));
		setGlobalCanvasMode("leads");

		// Trigger pulse highlight animation on Right Panel
		setCanvasHighlight(Date.now());
	};

	return (
		<div className={cn("my-2.5 not-prose select-none", className)}>
			{/* Compact Card Deck Item */}
			<div
				className={cn(
					"w-full flex items-center justify-between px-3 py-2 rounded-lg border transition-all shadow-2xs group",
					isActive
						? "bg-emerald-500/5 border-emerald-500/30 hover:bg-emerald-500/10 dark:bg-emerald-950/20 dark:border-emerald-800/40"
						: "bg-card border-border/80 hover:bg-muted/50 hover:border-border"
				)}
			>
				<button
					type="button"
					onClick={handlePingRightPanel}
					className="flex items-center gap-2.5 min-w-0 flex-1 text-left cursor-pointer focus:outline-none"
				>
					<div
						className={cn(
							"size-7 rounded-md flex items-center justify-center shrink-0 border transition-colors",
							isActive
								? "bg-emerald-500/15 border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
								: "bg-muted/80 border-border/50 text-muted-foreground group-hover:text-foreground"
						)}
					>
						<TableIcon className="size-3.5" />
					</div>

					<div className="min-w-0 flex-1">
						<div className="text-[12px] font-medium text-foreground truncate group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
							{title}
						</div>
						<div className="flex items-center gap-1.5 mt-0.5">
							<span className="font-mono text-[9px] font-bold px-1 py-0.2 rounded bg-muted/90 text-muted-foreground uppercase tracking-wider">
								{type}
							</span>
							{typeof rowCount === "number" && (
								<span className="text-[10px] text-muted-foreground">
									• {rowCount} {rowCount === 1 ? "kết quả" : "kết quả"}
								</span>
							)}
						</div>
					</div>
				</button>

				<div className="flex items-center gap-2 shrink-0 ml-2">
					{/* Status viewing badge */}
					{isActive && (
						<span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border border-emerald-500/20">
							<span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
							Đang xem
						</span>
					)}

					{/* Optional inline peek expander */}
					{children && (
						<button
							type="button"
							onClick={() => setIsInlineExpanded((prev) => !prev)}
							className="p-1 rounded text-muted-foreground/60 hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
							title={isInlineExpanded ? "Thu gọn bảng inline" : "Xem bảng inline"}
						>
							<ChevronDown
								className={cn(
									"size-3.5 transition-transform duration-200",
									isInlineExpanded && "rotate-180"
								)}
							/>
						</button>
					)}

					<button
						type="button"
						onClick={handlePingRightPanel}
						className="p-0.5 rounded text-muted-foreground/60 group-hover:text-foreground transition-all cursor-pointer focus:outline-none"
						title="Chuyển sang Bảng Leads bên phải"
					>
						<ChevronRight className="size-3.5 group-hover:translate-x-0.5 transition-transform" />
					</button>
				</div>
			</div>

			{/* Inline Expanded Raw Table (Only when user explicitly clicks the expand icon) */}
			{isInlineExpanded && children && (
				<div className="mt-2 p-2 rounded-md border border-border/70 bg-muted/20 overflow-x-auto text-[11px] animate-in fade-in slide-in-from-top-1 duration-200">
					{children}
				</div>
			)}
		</div>
	);
};
