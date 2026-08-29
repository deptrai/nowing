"use client";

import { useCallback, useEffect, useState } from "react";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { isPublicRoute } from "@/lib/auth-utils";
import { buildBackendUrl } from "@/lib/env-config";

type SessionState =
	| {
			status: "loading";
			authenticated: false;
			accessExpiresAt: null;
			isImpersonation: false;
			impersonatedBy: null;
			targetUser: null;
	  }
	| {
			status: "authenticated";
			authenticated: true;
			accessExpiresAt: number | null;
			isImpersonation: boolean;
			impersonatedBy: string | null;
			targetUser: string | null;
	  }
	| {
			status: "unauthenticated";
			authenticated: false;
			accessExpiresAt: null;
			isImpersonation: false;
			impersonatedBy: null;
			targetUser: null;
	  };

export function useSession() {
	const [state, setState] = useState<SessionState>({
		status: "loading",
		authenticated: false,
		accessExpiresAt: null,
		isImpersonation: false,
		impersonatedBy: null,
		targetUser: null,
	});

	const refresh = useCallback(async () => {
		try {
			const response = await authenticatedFetch(buildBackendUrl("/auth/session"), {
				skipAuthRedirect: true,
			});
			if (!response.ok) {
				setState({
					status: "unauthenticated",
					authenticated: false,
					accessExpiresAt: null,
					isImpersonation: false,
					impersonatedBy: null,
					targetUser: null,
				});
				return;
			}
			const data = (await response.json()) as {
				authenticated: boolean;
				access_expires_at: number | null;
				is_impersonation: boolean;
				impersonated_by: string | null;
				target_user: string | null;
			};
			setState({
				status: "authenticated",
				authenticated: true,
				accessExpiresAt: data.access_expires_at,
				isImpersonation: data.is_impersonation,
				impersonatedBy: data.impersonated_by,
				targetUser: data.target_user,
			});
		} catch {
			setState({
				status: "unauthenticated",
				authenticated: false,
				accessExpiresAt: null,
				isImpersonation: false,
				impersonatedBy: null,
				targetUser: null,
			});
		}
	}, []);

	useEffect(() => {
		// Public routes do not need an active session; skip the /auth/session
		// call to avoid noisy 401 console errors for unauthenticated visitors.
		if (typeof window !== "undefined" && isPublicRoute(window.location.pathname)) {
			setState({
				status: "unauthenticated",
				authenticated: false,
				accessExpiresAt: null,
				isImpersonation: false,
				impersonatedBy: null,
				targetUser: null,
			});
			return;
		}
		void refresh();
	}, [refresh]);

	return { ...state, refresh };
}
