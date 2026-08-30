"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { AlertCircle, X } from "lucide-react";
import type { FC } from "react";
import { currentThreadAtom } from "@/atoms/chat/current-thread.atom";
import {
	clearPremiumAlertForThreadAtom,
	premiumAlertByThreadAtom,
} from "@/atoms/chat/premium-alert.atom";
import { Button } from "@/components/ui/button";

export const PremiumQuotaPinnedAlert: FC = () => {
	const currentThreadState = useAtomValue(currentThreadAtom);
	const alertsByThread = useAtomValue(premiumAlertByThreadAtom);
	const clearPremiumAlertForThread = useSetAtom(clearPremiumAlertForThreadAtom);

	const currentThreadId = currentThreadState?.id;
	if (!currentThreadId) return null;

	const alert = alertsByThread[currentThreadId];
	if (!alert) return null;

	return (
		<div className="mx-0 overflow-hidden rounded-2xl border-input bg-muted px-4 py-4 text-foreground select-none">
			<div className="flex items-center gap-2">
				<AlertCircle className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
				<div className="min-w-0 flex-1">
					<p className="text-sm">{alert.message}</p>
				</div>
				<Button
					type="button"
					variant="ghost"
					size="icon"
					className="size-6 text-muted-foreground hover:bg-transparent hover:text-accent-foreground"
					aria-label="Dismiss premium quota alert"
					onClick={() => clearPremiumAlertForThread(currentThreadId)}
				>
					<X className="size-4" aria-hidden="true" />
				</Button>
			</div>
		</div>
	);
};
