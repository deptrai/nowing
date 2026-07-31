"use client";

import { useEffect, useState } from "react";
import { USER_QUERY_KEY } from "@/atoms/user/user-query.atoms";
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
			<div className="flex-1 min-h-0">{children}</div>
		</div>
	);
}
