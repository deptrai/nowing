import { GovernanceConsole } from "@/components/governance/governance-console";

export default async function Page({ params }: { params: Promise<{ workspace_id: string }> }) {
	const { workspace_id } = await params;
	return <GovernanceConsole workspaceId={Number(workspace_id)} />;
}
