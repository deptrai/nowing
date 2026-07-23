import { DataRetentionManager } from "@/components/settings/data-retention-manager";

export default async function Page({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await params;
	return <DataRetentionManager workspaceId={Number(workspace_id)} />;
}
