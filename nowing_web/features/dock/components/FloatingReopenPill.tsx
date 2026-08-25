"use client";

import { useSetAtom } from "jotai";
import { PanelRightOpen } from "lucide-react";
import { dockOpenAtom } from "@/atoms/layout/dock.atom";
import { Button } from "@/components/ui/button";

export function FloatingReopenPill({ tabs }: { tabs: { hasUpdate: boolean }[] }) {
	const setOpen = useSetAtom(dockOpenAtom);
	const updateCount = tabs.filter((t) => t.hasUpdate).length;

	return (
		<Button
			type="button"
			variant="outline"
			size="sm"
			onClick={() => setOpen(true)}
			className="absolute top-3 right-3 z-50 h-8 gap-1.5 rounded-full border bg-background/95 px-3 text-xs font-medium shadow-md backdrop-blur hover:bg-accent hover:text-accent-foreground"
		>
			<PanelRightOpen className="size-3.5" aria-hidden="true" />
			<span>Open canvas</span>
			{updateCount > 0 && (
				<span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-emerald-500 px-1 text-[10px] font-bold text-white">
					{updateCount > 9 ? "9+" : updateCount}
				</span>
			)}
		</Button>
	);
}
