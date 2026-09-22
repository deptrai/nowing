"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { useCallback } from "react";
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

interface AuthSessionPayload {
	authenticated: boolean;
	access_expires_at: number | null;
	is_impersonation: boolean;
	impersonated_by: string | null;
	target_user: string | null;
}

async function fetchSession(): Promise<SessionState> {
	try {
		const response = await authenticatedFetch(buildBackendUrl("/auth/session"), {
			skipAuthRedirect: true,
		});
		if (!response.ok) {
			if (response.status === 401 || response.status === 403) {
				return {
					status: "unauthenticated",
					authenticated: false,
					accessExpiresAt: null,
					isImpersonation: false,
					impersonatedBy: null,
					targetUser: null,
				};
			}
			throw new Error(`Session check failed with status ${response.status}`);
		}
		const data = (await response.json()) as AuthSessionPayload;
		if (!data.authenticated) {
			return {
				status: "unauthenticated",
				authenticated: false,
				accessExpiresAt: null,
				isImpersonation: false,
				impersonatedBy: null,
				targetUser: null,
			};
		}
		return {
			status: "authenticated",
			authenticated: true,
			accessExpiresAt: data.access_expires_at,
			isImpersonation: data.is_impersonation,
			impersonatedBy: data.impersonated_by,
			targetUser: data.target_user,
		};
	} catch (error) {
		if (error instanceof Error && error.message.includes("Session check failed with status")) {
			throw error;
		}
		return {
			status: "unauthenticated",
			authenticated: false,
			accessExpiresAt: null,
			isImpersonation: false,
			impersonatedBy: null,
			targetUser: null,
		};
	}
}

export function useSession() {
	const queryClient = useQueryClient();
	const pathname = usePathname();
	const isClient = typeof window !== "undefined";
	const isPublic = isClient && isPublicRoute(pathname || "");

	const { data, isLoading } = useQuery({
		queryKey: ["auth-session"],
		queryFn: fetchSession,
		enabled: isClient && !isPublic,
		staleTime: 5 * 60 * 1000,
		gcTime: 10 * 60 * 1000,
	});

	const refresh = useCallback(async () => {
		await queryClient.invalidateQueries({ queryKey: ["auth-session"] });
	}, [queryClient]);

	if (isClient && isPublic) {
		return {
			status: "unauthenticated" as const,
			authenticated: false as const,
			accessExpiresAt: null,
			isImpersonation: false as const,
			impersonatedBy: null,
			targetUser: null,
			refresh,
		};
	}

	if (!isClient || isLoading || !data) {
		return {
			status: "loading" as const,
			authenticated: false as const,
			accessExpiresAt: null,
			isImpersonation: false as const,
			impersonatedBy: null,
			targetUser: null,
			refresh,
		};
	}

	return {
		...data,
		refresh,
	};
}
