"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { USER_QUERY_KEY } from "@/atoms/user/user-query.atoms";
import { ImpersonationBanner } from "@/components/admin/ImpersonationBanner";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";
import { useSession } from "@/hooks/use-session";
import { redirectToLogin } from "@/lib/auth-utils";
import { queryClient } from "@/lib/query-client/client";

export function AdminShell({ children }: { children: React.ReactNode }) {
	const [isCheckingAuth, setIsCheckingAuth] = useState(true);
	const session = useSession();

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

	if (isCheckingAuth) {
		return null;
	}

	return (
		<div className="h-full flex flex-col">
			{session.status === "authenticated" && session.isImpersonation && <ImpersonationBanner />}
			<nav className="bg-gray-900 text-white px-4 py-2 flex gap-4 text-sm">
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
			</nav>
			<div className="flex-1 min-h-0">{children}</div>
		</div>
	);
}
