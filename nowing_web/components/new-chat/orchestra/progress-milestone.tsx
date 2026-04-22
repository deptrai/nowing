"use client";

import { useEffect, useRef } from "react";
import { useSetAtom } from "jotai";
import { orchestraStateAtom } from "@/atoms/chat/orchestra.atom";
import { Loader2 } from "lucide-react";

interface ProgressMilestoneProps {
	sessionId: string;
	milestone?: string;
	milestone30sFired: boolean;
	elapsedMs: number;
}

export function ProgressMilestone({
	sessionId,
	milestone,
	milestone30sFired,
	elapsedMs,
}: ProgressMilestoneProps) {
	const setOrchestra = useSetAtom(orchestraStateAtom);
	const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	// Fire T+30s milestone once per session
	useEffect(() => {
		if (milestone30sFired) return;

		const remaining = 30_000 - elapsedMs;
		if (remaining <= 0) {
			// Already past 30s — mark fired without showing banner (session may be near complete)
			setOrchestra((prev) => {
				const sessions = new Map(prev.sessions);
				const session = sessions.get(sessionId);
				if (!session) return prev;
				sessions.set(sessionId, { ...session, milestone30sFired: true });
				return { ...prev, sessions };
			});
			return;
		}

		timerRef.current = setTimeout(() => {
			setOrchestra((prev) => {
				const sessions = new Map(prev.sessions);
				const session = sessions.get(sessionId);
				if (!session) return prev;
				sessions.set(sessionId, { ...session, milestone30sFired: true });
				return { ...prev, sessions };
			});
		}, remaining);

		return () => {
			if (timerRef.current) clearTimeout(timerRef.current);
		};
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [sessionId, milestone30sFired]);

	// Only render the inline text banner after 30s
	if (!milestone30sFired) return null;

	return (
		<div className="flex items-center gap-1.5 text-xs text-muted-foreground px-1 py-0.5">
			<Loader2 className="h-3 w-3 animate-spin shrink-0" />
			<span>{milestone ?? "Analysing in depth…"}</span>
		</div>
	);
}
