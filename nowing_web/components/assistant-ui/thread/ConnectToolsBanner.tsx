"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { Unplug, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { type FC, useEffect, useState } from "react";
import { connectorDialogOpenAtom } from "@/atoms/connector-dialog/connector-dialog.atoms";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { Avatar, AvatarFallback, AvatarGroup } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { BANNER_CONNECTORS, BANNER_DISMISSED_KEY } from "./constants";

export const ConnectToolsBanner: FC<{
	isThreadEmpty: boolean;
	onVisibleChange?: (visible: boolean) => void;
}> = ({ isThreadEmpty, onVisibleChange }) => {
	const { data: connectors } = useAtomValue(connectorsAtom);
	const setConnectorDialogOpen = useSetAtom(connectorDialogOpenAtom);
	const [dismissed, setDismissed] = useState(() => {
		if (typeof window === "undefined") return false;
		return localStorage.getItem(BANNER_DISMISSED_KEY) === "true";
	});
	const [dismissRequested, setDismissRequested] = useState(false);

	const hasConnectors = (connectors?.length ?? 0) > 0;
	const isVisible = !dismissed && !hasConnectors && isThreadEmpty;
	const shouldShowTray = isVisible && !dismissRequested;

	useEffect(() => {
		onVisibleChange?.(isVisible);
	}, [isVisible, onVisibleChange]);

	const handleDismiss = (e: React.MouseEvent) => {
		e.stopPropagation();
		setDismissRequested(true);
	};

	return (
		<AnimatePresence
			initial={false}
			onExitComplete={() => {
				if (!dismissRequested) return;
				setDismissed(true);
				localStorage.setItem(BANNER_DISMISSED_KEY, "true");
			}}
		>
			{shouldShowTray ? (
				<motion.div
					key="connect-tools-tray"
					initial={{ opacity: 0, y: -10 }}
					animate={{ opacity: 1, y: 0 }}
					exit={{ opacity: 0, y: -14 }}
					transition={{ duration: 0.18, ease: "easeOut" }}
					className="relative z-0 -mt-5 flex min-w-0 items-center gap-2 rounded-b-3xl border border-input bg-muted/40 px-4 pt-7 pb-3 shadow-sm shadow-black/5 dark:shadow-black/10"
				>
					<Button
						type="button"
						variant="ghost"
						size="sm"
						className="h-7 min-w-0 cursor-pointer justify-start gap-2 rounded-md px-0 text-[13px] font-normal text-muted-foreground select-none hover:bg-transparent hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
						onClick={() => setConnectorDialogOpen(true)}
						title="Connect your tools"
					>
						<Unplug className="size-4 shrink-0" aria-hidden="true" />
						<span className="truncate">Connect your tools</span>
					</Button>
					<div className="min-w-0 flex-1" />
					<AvatarGroup className="shrink-0" aria-hidden="true">
						{BANNER_CONNECTORS.map(({ type }, i) => (
							<Avatar
								key={type}
								className="size-5"
								style={{ zIndex: BANNER_CONNECTORS.length - i }}
								aria-hidden="true"
							>
								<AvatarFallback className="bg-accent text-[10px]">
									{getConnectorIcon(type, "size-3")}
								</AvatarFallback>
							</Avatar>
						))}
					</AvatarGroup>
					<Button
						type="button"
						onClick={handleDismiss}
						variant="ghost"
						size="icon"
						className="size-7 shrink-0 cursor-pointer rounded-md text-muted-foreground hover:bg-transparent hover:text-foreground"
						aria-label="Dismiss"
						title="Dismiss"
					>
						<X className="size-3.5" aria-hidden="true" />
					</Button>
				</motion.div>
			) : null}
		</AnimatePresence>
	);
};
