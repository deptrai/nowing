import type { Metadata } from "next";
import { WorkspaceHealthDashboard } from "@/components/analytics/workspace-health-dashboard";

export const metadata: Metadata = {
	title: "Workspace Health & Analytics | Nowing",
	description: "Workspace adoption sparklines, knowledge coverage, and quota telemetry",
};

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
