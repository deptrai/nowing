"use client";

import { useAtom } from "jotai";
import { useMemo } from "react";
import { dockOpenAtom, dockVerboseModeAtom } from "@/atoms/layout/dock.atom";
import { Drawer, DrawerContent, DrawerHandle } from "@/components/ui/drawer";
import { cn } from "@/lib/utils";
import type { DockTab } from "../hooks/useDockTabs";
import { DockBody, type DockBodyProps } from "./DockBody";
import { DockHeader } from "./DockHeader";

interface MobileDockSheetProps extends DockBodyProps {
	tabs: DockTab[];
}

const MOBILE_COMPOSER_OFFSET = "calc(5.5rem + env(safe-area-inset-bottom))";

function useHandleLabel(tabs: DockTab[]) {
	return useMemo(() => {
		if (tabs.length === 0) return "0 tabs";
		if (tabs.length === 1) return tabs[0]?.label ?? "1 tab";
		const first = tabs[0]?.label ?? "";
		const second = tabs[1]?.label ?? "";
		if (tabs.length === 2) return `${first} · ${second}`;
		return `${first} · ${second} +${tabs.length - 2}`;
	}, [tabs]);
}

export function MobileDockSheet({ tabs, ...bodyProps }: MobileDockSheetProps) {
	const [isOpen, setIsOpen] = useAtom(dockOpenAtom);
	const [verbose] = useAtom(dockVerboseModeAtom);
	const handleLabel = useHandleLabel(tabs);

	if (tabs.length === 0) return null;

	return (
		<>
			{!isOpen && (
				<div
					className="fixed inset-x-0 z-[70] flex justify-center pointer-events-none"
					style={{ bottom: MOBILE_COMPOSER_OFFSET }}
				>
					<button
						type="button"
						onClick={() => setIsOpen(true)}
						className={cn(
							"pointer-events-auto flex h-9 max-w-[80%] items-center gap-2 rounded-full border border-border bg-background/95 px-4 shadow-lg backdrop-blur",
							"active:bg-muted transition-colors"
						)}
					>
						<span className="h-1 w-8 shrink-0 rounded-full bg-muted-foreground/40" />
						<span className="truncate text-xs font-medium text-muted-foreground">
							{handleLabel}
						</span>
					</button>
				</div>
			)}

			<Drawer open={isOpen} onOpenChange={setIsOpen} modal={false} dismissible>
				<DrawerContent
					overlayClassName="bg-transparent pointer-events-none"
					className="pointer-events-auto z-[70] mx-auto flex h-[50dvh] max-h-[70dvh] max-w-lg flex-col"
					style={{ marginBottom: MOBILE_COMPOSER_OFFSET }}
				>
					<DrawerHandle />
					<DockHeader tabs={tabs} />
					<div
						id="dock-tabpanel"
						role="tabpanel"
						aria-labelledby={`dock-tab-${bodyProps.activeTab}`}
						data-vaul-no-drag
						className={cn(
							"min-h-0 flex-1 touch-pan-y overflow-hidden transition-opacity",
							verbose && "opacity-60"
						)}
					>
						<DockBody {...bodyProps} />
					</div>
				</DrawerContent>
			</Drawer>
		</>
	);
}
