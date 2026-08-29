// Server component

import type { Metadata } from "next";
import type React from "react";
import { DashboardClientLayout } from "./client-layout";

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
	const { workspace_id } = await params;

	return (
		<DashboardClientLayout workspaceId={workspace_id}>
			{children}
		</DashboardClientLayout>
	);
}
