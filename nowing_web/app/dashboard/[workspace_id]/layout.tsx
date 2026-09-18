// Server component

import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import type React from "react";
import { DashboardClientLayout } from "./client-layout";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("dashboard");
	return {
		title: { default: t("layout_default_title"), template: t("layout_title_template") },
		description: t("layout_description"),
	};
}
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
