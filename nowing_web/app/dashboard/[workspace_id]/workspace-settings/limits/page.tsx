"use client";

import { WorkspaceLimitsManager } from "@/components/settings/workspace-limits-manager";

interface LimitsPageProps {
	params: Promise<{ workspace_id: string }>;
}

export default async function LimitsPage({ params }: LimitsPageProps) {
	const { workspace_id } = await params;
	return <WorkspaceLimitsManager workspaceId={workspace_id} />;
}
