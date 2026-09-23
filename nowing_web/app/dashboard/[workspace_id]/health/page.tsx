import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { WorkspaceHealthDashboard } from "@/components/analytics/workspace-health-dashboard";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("analytics");
	return {
		title: t("health_meta_title"),
		description: t("health_meta_description"),
	};
}

interface HealthPageProps {
	params: Promise<{
		workspace_id: string;
	}>;
}

export default async function WorkspaceHealthPage({ params }: HealthPageProps) {
	const { workspace_id } = await params;

	return (
		<div className="w-full max-w-7xl mx-auto py-6 px-4 sm:px-6">
			<WorkspaceHealthDashboard workspaceId={workspace_id} />
		</div>
	);
}
