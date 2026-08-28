"use client";

import { useAtom, useSetAtom } from "jotai";
import { Expand, MessageSquare, PanelRightOpen, Shrink, X } from "lucide-react";
import {
	type DockTabId,
	dockActiveTabAtom,
	dockExpandedAtom,
	dockOpenAtom,
	dockVerboseModeAtom,
} from "@/atoms/layout/dock.atom";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { DockTab as DockTabType } from "../hooks/useDockTabs";
import { DockTab } from "./DockTab";

interface DockHeaderProps {
	tabs: DockTabType[];
}

const TAB_ORDER: DockTabId[] = [
	"leads",
	"web-builder",
	"research",
	"reports",
	"images",
	"media",
	"data",
	"charts",
	"code",
	"sources",
	"artifacts",
	"slides",
];

export function DockHeader({ tabs }: DockHeaderProps) {
	const [activeTab, setActiveTab] = useAtom(dockActiveTabAtom);
	const setOpen = useSetAtom(dockOpenAtom);
	const [verbose, setVerbose] = useAtom(dockVerboseModeAtom);
	const [isExpanded, setIsExpanded] = useAtom(dockExpandedAtom);

	const sortedTabs = [...tabs].sort((a, b) => {
		const ai = TAB_ORDER.indexOf(a.id as DockTabId);
		const bi = TAB_ORDER.indexOf(b.id as DockTabId);
		return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
	});

	return (
		<div className="shrink-0 h-9 border-b border-border/80 bg-muted/40 flex items-center justify-between px-2 select-none">
			<div className="flex items-center gap-1 min-w-0">
				<Tooltip>
					<TooltipTrigger asChild>
						<Button
							type="button"
							variant="ghost"
							size="icon"
							onClick={() => setOpen(false)}
							className="size-7 -ml-1 text-muted-foreground hover:text-foreground hover:bg-muted"
						>
							<X className="size-3.5" aria-hidden="true" />
							<span className="sr-only">Close canvas</span>
						</Button>
					</TooltipTrigger>
					<TooltipContent side="bottom">Close canvas</TooltipContent>
				</Tooltip>

				<Tooltip>
					<TooltipTrigger asChild>
						<Button
							type="button"
							variant="ghost"
							size="icon"
							onClick={() => setIsExpanded((v) => !v)}
							className="size-7 -ml-1 text-muted-foreground hover:text-foreground hover:bg-muted"
						>
							{isExpanded ? (
								<Shrink className="size-3.5" aria-hidden="true" />
							) : (
								<Expand className="size-3.5" aria-hidden="true" />
							)}
							<span className="sr-only">
								{isExpanded ? "Thu nhỏ panel" : "Mở rộng panel"}
							</span>
						</Button>
					</TooltipTrigger>
					<TooltipContent side="bottom">
						{isExpanded ? "Thu nhỏ panel" : "Mở rộng panel"}
					</TooltipContent>
				</Tooltip>

				<div
					role="tablist"
					aria-label="Dock tabs"
					className="flex flex-1 items-center gap-0.5 overflow-x-auto no-scrollbar min-w-0"
				>
					{sortedTabs.map((tab) => (
						<DockTab
							key={tab.id}
							id={tab.id}
							label={tab.label}
							isActive={activeTab === tab.id}
							hasUpdate={tab.hasUpdate}
							onClick={() => setActiveTab(tab.id as DockTabId)}
						/>
					))}
				</div>
			</div>

			<Tooltip>
				<TooltipTrigger asChild>
					{/* ponytail: verbose toggle persists state but does not yet reroute rich content back into the chat stream. */}
					<Button
						type="button"
						variant="ghost"
						size="icon"
						onClick={() => setVerbose((v) => !v)}
						className={cn(
							"size-7 text-muted-foreground hover:text-foreground hover:bg-muted",
							verbose && "text-amber-600 bg-amber-500/10 hover:bg-amber-500/20"
						)}
					>
						{verbose ? (
							<MessageSquare className="size-3.5" aria-hidden="true" />
						) : (
							<PanelRightOpen className="size-3.5" aria-hidden="true" />
						)}
						<span className="sr-only">Toggle verbose mode</span>
					</Button>
				</TooltipTrigger>
				<TooltipContent side="bottom">
					{verbose ? "Rich output shown in chat" : "Show full output in chat"}
				</TooltipContent>
			</Tooltip>
		</div>
	);
}
