"use client";

import { useAtomValue } from "jotai";
import Link from "next/link";
import { useEffect, useState } from "react";
import { currentUserAtom, USER_QUERY_KEY } from "@/atoms/user/user-query.atoms";
import { ImpersonationBanner } from "@/components/admin/ImpersonationBanner";
import { BroadcastBanner } from "@/components/broadcasts/BroadcastBanner";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";
import { useSession } from "@/hooks/use-session";
import { redirectToLogin } from "@/lib/auth-utils";
import { queryClient } from "@/lib/query-client/client";

export function AdminShell({ children }: { children: React.ReactNode }) {
	const [isCheckingAuth, setIsCheckingAuth] = useState(true);
	const session = useSession();
	const userResult = useAtomValue(currentUserAtom);
	const user = userResult?.data;

	useGlobalLoadingEffect(isCheckingAuth);

	useEffect(() => {
		async function checkAuth() {
			if (session.status === "loading") return;
			if (session.status === "unauthenticated") {
				redirectToLogin();
				return;
			}
			queryClient.invalidateQueries({ queryKey: [...USER_QUERY_KEY] });
			setIsCheckingAuth(false);
		}
		void checkAuth();
	}, [session.status]);

	if (isCheckingAuth || (session.status === "authenticated" && userResult.isLoading)) {
		return null;
	}

	if (session.status === "authenticated" && user && !user.is_superuser) {
		return (
			<div className="flex h-full flex-col items-center justify-center gap-4 p-6 text-center">
				<h1 className="text-2xl font-semibold">Access Denied</h1>
				<p className="text-muted-foreground">
					You must have superuser administrative privileges to view this area.
				</p>
				<Link href="/dashboard" className="text-sm text-primary underline">
					Return to Dashboard
				</Link>
			</div>
		);
	}

	return (
		<div className="h-full flex flex-col">
			{session.status === "authenticated" && session.isImpersonation && <ImpersonationBanner />}
			<BroadcastBanner />
			<nav className="bg-gray-900 text-white px-4 py-2 flex flex-wrap gap-4 text-sm">
				<Link href="/admin/users" className="hover:underline">
					Users
				</Link>
				<Link href="/admin/workspaces" className="hover:underline">
					Workspaces
				</Link>
				<Link href="/admin/affiliates/payouts" className="hover:underline">
					Affiliates & Payouts
				</Link>
				<Link href="/admin/credits" className="hover:underline">
					Credits
				</Link>
				<Link href="/admin/telemetry" className="hover:underline">
					Telemetry
				</Link>
				<Link href="/admin/scrapers/rules" className="hover:underline">
					Scraper Rules
				</Link>
				<Link href="/admin/audit-logs" className="hover:underline">
					Audit Logs
				</Link>
				<Link href="/admin/dnc" className="hover:underline">
					DNC Blacklist
				</Link>
				<Link href="/admin/broadcasts" className="hover:underline">
					Broadcasts
				</Link>
			</nav>
			<div className="flex-1 min-h-0">{children}</div>
		</div>
	);
}
