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
import { useTranslations } from "next-intl";

export function AdminShell({ children }: { children: React.ReactNode }) {
	const t = useTranslations("admin");
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
				<h1 className="text-2xl font-semibold">{t("access_denied")}</h1>
				<p className="text-muted-foreground">
					{t("access_denied_desc")}
				</p>
				<Link href="/dashboard" className="text-sm text-primary underline">
					{t("return_to_dashboard")}
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
					{t("nav_users")}
				</Link>
				<Link href="/admin/workspaces" className="hover:underline">
					{t("nav_workspaces")}
				</Link>
				<Link href="/admin/saas/plans" className="hover:underline">
					{t("nav_saas_plans")}
				</Link>
				<Link href="/admin/saas/bulk-ops" className="hover:underline">
					{t("nav_bulk_ops")}
				</Link>
				<Link href="/admin/affiliates/payouts" className="hover:underline">
					{t("nav_affiliates_payouts")}
				</Link>
				<Link href="/admin/credits" className="hover:underline">
					{t("nav_credits")}
				</Link>
				<Link href="/admin/telemetry" className="hover:underline">
					{t("nav_telemetry")}
				</Link>
				<Link href="/admin/scrapers/rules" className="hover:underline">
					{t("nav_scraper_rules")}
				</Link>
				<Link href="/admin/global-model-connections" className="hover:underline">
					{t("nav_global_models")}
				</Link>
				<Link href="/admin/audit-logs" className="hover:underline">
					{t("nav_audit_logs")}
				</Link>
				<Link href="/admin/dnc" className="hover:underline">
					{t("nav_dnc_blacklist")}
				</Link>
				<Link href="/admin/broadcasts" className="hover:underline">
					{t("nav_broadcasts")}
				</Link>
			</nav>
			<div className="flex-1 min-h-0">{children}</div>
		</div>
	);
}
