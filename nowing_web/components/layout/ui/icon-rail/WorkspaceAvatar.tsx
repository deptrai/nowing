"use client";

import { Settings, Trash2, Users } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type { MouseEvent } from "react";
import { useCallback, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface WorkspaceAvatarProps {
	name: string;
	href?: string;
	prefetch?: boolean;
	isActive?: boolean;
	isShared?: boolean;
	isOwner?: boolean;
	onClick?: () => void;
	onDelete?: () => void;
	onSettings?: () => void;
	size?: "sm" | "md";
	disableTooltip?: boolean;
}

/**
 * Generates a consistent color based on workspace name
 */
function stringToColor(str: string): string {
	let hash = 0;
	for (let i = 0; i < str.length; i++) {
		hash = str.charCodeAt(i) + ((hash << 5) - hash);
	}
	const colors = [
		"#6366f1", // indigo
		"#22c55e", // green
		"#f59e0b", // amber
		"#ef4444", // red
		"#8b5cf6", // violet
		"#06b6d4", // cyan
		"#ec4899", // pink
		"#14b8a6", // teal
	];
	return colors[Math.abs(hash) % colors.length];
}

/**
 * Gets initials from workspace name (max 2 chars)
 */
function getInitials(name: string): string {
	const words = name.trim().split(/\s+/);
	if (words.length >= 2) {
		return (words[0][0] + words[1][0]).toUpperCase();
	}
	return name.slice(0, 2).toUpperCase();
}

export function WorkspaceAvatar({
	name,
	href,
	prefetch = true,
	isActive,
	isShared,
	isOwner = true,
	onClick,
	onDelete,
	onSettings,
	size = "md",
	disableTooltip = false,
}: WorkspaceAvatarProps) {
	const t = useTranslations("workspace");
	const tCommon = useTranslations("common");
	const bgColor = stringToColor(name);
	const initials = getInitials(name);
	const sizeClasses = size === "sm" ? "h-8 w-8 text-xs" : "h-10 w-10 text-sm";

	const [menuOpen, setMenuOpen] = useState(false);
	const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
	const touchMoved = useRef(false);

	const openMenu = useCallback(() => {
		setMenuOpen(true);
	}, []);

	const handleContextMenu = useCallback(
		(event: MouseEvent<HTMLButtonElement | HTMLAnchorElement>) => {
			event.preventDefault();
			event.stopPropagation();
			setMenuOpen(true);
		},
		[]
	);

	const handleTouchStart = useCallback(() => {
		touchMoved.current = false;
		longPressTimer.current = setTimeout(() => {
			if (!touchMoved.current) {
				openMenu();
			}
		}, 500);
	}, [openMenu]);

	const handleTouchMove = useCallback(() => {
		touchMoved.current = true;
		if (longPressTimer.current) {
			clearTimeout(longPressTimer.current);
			longPressTimer.current = null;
		}
	}, []);

	const handleTouchEnd = useCallback(() => {
		if (longPressTimer.current) {
			clearTimeout(longPressTimer.current);
			longPressTimer.current = null;
		}
	}, []);

	const tooltipContent = (
		<div className="flex flex-col">
			<span>{name}</span>
			{isShared && (
				<span className="text-xs text-muted-foreground">
					{isOwner ? tCommon("owner") : tCommon("shared")}
				</span>
			)}
		</div>
	);

	const avatarClasses = cn(
		"relative inline-flex items-center justify-center rounded-lg font-semibold text-white transition-all select-none",
		"hover:text-white hover:opacity-90 active:scale-[0.98] active:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
		sizeClasses,
		isActive && "ring-2 ring-primary ring-offset-1 ring-offset-rail"
	);

	const avatarChildren = (
		<>
			{initials}
			{/* Shared indicator badge */}
			{isShared && (
				<span
					className={cn(
						"absolute -top-1 -right-1 flex items-center justify-center rounded-full bg-gray-800 text-white shadow-sm",
						size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4"
					)}
					title={tCommon("shared")}
				>
					<Users className={cn(size === "sm" ? "size-2" : "size-2.5")} />
				</span>
			)}
		</>
	);

	const avatarButton = (withMenuHandlers = false) => {
		if (href) {
			return (
				<Link
					href={href}
					prefetch={prefetch}
					onClick={onClick}
					onPointerDown={
						withMenuHandlers
							? (event) => {
									if (event.button === 0) {
										event.preventDefault();
									}
								}
							: undefined
					}
					onContextMenu={withMenuHandlers ? handleContextMenu : undefined}
					onTouchStart={withMenuHandlers ? handleTouchStart : undefined}
					onTouchMove={withMenuHandlers ? handleTouchMove : undefined}
					onTouchEnd={withMenuHandlers ? handleTouchEnd : undefined}
					onTouchCancel={withMenuHandlers ? handleTouchEnd : undefined}
					className={avatarClasses}
					style={{ backgroundColor: bgColor }}
				>
					{avatarChildren}
				</Link>
			);
		}

		return (
			<Button
				type="button"
				variant="ghost"
				size="icon"
				onClick={onClick}
				onPointerDown={
					withMenuHandlers
						? (event) => {
								if (event.button === 0) {
									event.preventDefault();
								}
							}
						: undefined
				}
				onContextMenu={withMenuHandlers ? handleContextMenu : undefined}
				onTouchStart={withMenuHandlers ? handleTouchStart : undefined}
				onTouchMove={withMenuHandlers ? handleTouchMove : undefined}
				onTouchEnd={withMenuHandlers ? handleTouchEnd : undefined}
				onTouchCancel={withMenuHandlers ? handleTouchEnd : undefined}
				className={avatarClasses}
				style={{ backgroundColor: bgColor }}
			>
				{avatarChildren}
			</Button>
		);
	};

	const menuItems = (
		<>
			{onSettings && (
				<DropdownMenuItem onClick={onSettings}>
					<Settings className="mr-2 h-4 w-4" />
					{tCommon("settings")}
				</DropdownMenuItem>
			)}
			{onDelete && isOwner && (
				<DropdownMenuItem onClick={onDelete}>
					<Trash2 className="mr-2 h-4 w-4" />
					{tCommon("delete")}
				</DropdownMenuItem>
			)}
			{onDelete && !isOwner && (
				<DropdownMenuItem onClick={onDelete}>
					<Trash2 className="mr-2 h-4 w-4" />
					{t("leave")}
				</DropdownMenuItem>
			)}
		</>
	);

	// If delete or settings handlers are provided, expose them through a dropdown menu.
	if (onDelete || onSettings) {
		const trigger = <DropdownMenuTrigger asChild>{avatarButton(true)}</DropdownMenuTrigger>;

		return (
			<DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
				{disableTooltip ? (
					trigger
				) : (
					<Tooltip>
						<TooltipTrigger asChild>{trigger}</TooltipTrigger>
						<TooltipContent side="right" sideOffset={8}>
							{tooltipContent}
						</TooltipContent>
					</Tooltip>
				)}
				<DropdownMenuContent side="right" align="start">
					{menuItems}
				</DropdownMenuContent>
			</DropdownMenu>
		);
	}

	// No context menu needed
	if (disableTooltip) {
		return avatarButton();
	}

	return (
		<Tooltip>
			<TooltipTrigger asChild>{avatarButton()}</TooltipTrigger>
			<TooltipContent side="right" sideOffset={8}>
				{tooltipContent}
			</TooltipContent>
		</Tooltip>
	);
}
