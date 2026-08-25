"use client";

import { useAtom } from "jotai";
import { useCallback, useEffect, useRef, useState } from "react";
import { dockWidthAtom } from "@/atoms/layout/dock.atom";
import { canvasLeftWidthAtom } from "@/atoms/leads/leads-canvas.atoms";
import { cn } from "@/lib/utils";

const MIN_DOCK_WIDTH = 360;
const DEFAULT_DOCK_WIDTH = 420;
const CENTER_RESIZER_WIDTH = 6;
const RIGHT_EDGE_MARGIN = 16;

export function DockResizer() {
	const [width, setWidth] = useAtom(dockWidthAtom);
	const [leftWidth] = useAtom(canvasLeftWidthAtom);
	const [isDragging, setIsDragging] = useState(false);
	const startXRef = useRef(0);
	const startWidthRef = useRef(width);

	const computeMax = useCallback(() => {
		if (typeof window === "undefined") return Number.POSITIVE_INFINITY;
		return Math.max(
			MIN_DOCK_WIDTH,
			window.innerWidth - leftWidth - CENTER_RESIZER_WIDTH - RIGHT_EDGE_MARGIN
		);
	}, [leftWidth]);

	const clamp = useCallback(
		(value: number) => {
			const max = computeMax();
			return Math.min(Math.max(value, MIN_DOCK_WIDTH), max);
		},
		[computeMax]
	);

	// Re-clamp on window resize or left panel resize
	useEffect(() => {
		const handleResize = () => setWidth((prev) => clamp(prev));
		handleResize();
		window.addEventListener("resize", handleResize);
		return () => window.removeEventListener("resize", handleResize);
	}, [clamp, setWidth]);

	useEffect(() => {
		if (!isDragging) return;

		const onMove = (e: MouseEvent) => {
			const delta = startXRef.current - e.clientX;
			setWidth(clamp(startWidthRef.current + delta));
		};

		const onUp = () => setIsDragging(false);

		document.addEventListener("mousemove", onMove);
		document.addEventListener("mouseup", onUp, { once: true });
		document.body.classList.add("select-none", "cursor-col-resize");

		return () => {
			document.removeEventListener("mousemove", onMove);
			document.body.classList.remove("select-none", "cursor-col-resize");
		};
	}, [isDragging, clamp, setWidth]);

	const handleMouseDown = (e: React.MouseEvent) => {
		e.preventDefault();
		startXRef.current = e.clientX;
		startWidthRef.current = width;
		setIsDragging(true);
	};

	const handleDoubleClick = () => setWidth(DEFAULT_DOCK_WIDTH);

	const handleKeyDown = (e: React.KeyboardEvent) => {
		if (e.key === "ArrowLeft") {
			e.preventDefault();
			setWidth((prev) => clamp(prev - 20));
		} else if (e.key === "ArrowRight") {
			e.preventDefault();
			setWidth((prev) => clamp(prev + 20));
		}
	};

	const max = computeMax();

	return (
		<hr
			aria-label="Điều chỉnh kích thước panel phải"
			aria-valuenow={width}
			aria-valuemin={MIN_DOCK_WIDTH}
			aria-valuemax={max}
			aria-orientation="vertical"
			tabIndex={0}
			title="Kéo để điều chỉnh kích thước / Nhấp đúp để đặt lại 420px"
			onMouseDown={handleMouseDown}
			onDoubleClick={handleDoubleClick}
			onKeyDown={handleKeyDown}
			className={cn(
				"absolute left-0 top-9 bottom-0 w-1.5 z-50 cursor-col-resize border-0 bg-border hover:bg-emerald-500/80 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors",
				isDragging && "bg-emerald-500 shadow-md shadow-emerald-500/50"
			)}
		/>
	);
}
