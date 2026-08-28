// Server component

import type { Metadata } from "next";
import { cookies } from "next/headers";
import type React from "react";
import { DashboardClientLayout } from "./client-layout";

const PLAYGROUND_SIDEBAR_COLLAPSED_COOKIE = "nowing_playground_sidebar_collapsed";

export const metadata: Metadata = {
	title: { default: "Nowing Dashboard", template: "%s | Nowing Dashboard" },
	description: "Open-core long-term research memory for AI agents",
};

export default async function DashboardLayout({
	params,
	children,
}: {
	params: Promise<{ workspace_id: string }>;
	children: React.ReactNode;
}) {
	const [{ workspace_id }, cookieStore] = await Promise.all([params, cookies()]);
	const initialPlaygroundSidebarCollapsed =
		cookieStore.get(PLAYGROUND_SIDEBAR_COLLAPSED_COOKIE)?.value !== "false";

	return (
		<DashboardClientLayout
			workspaceId={workspace_id}
			initialPlaygroundSidebarCollapsed={initialPlaygroundSidebarCollapsed}
		>
			{children}
		</DashboardClientLayout>
	);
}
