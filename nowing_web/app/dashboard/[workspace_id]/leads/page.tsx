import { NowingSplitCanvas } from "@/components/leads/NowingSplitCanvas";

/**
 * Story 42.7: standalone Leads route — mounts the split canvas without a chat
 * thread so the leads matrix renders full-width (no AssistantRuntimeProvider).
 */
export default async function LeadsPage(props: { params: Promise<{ workspace_id: string }> }) {
	const { workspace_id } = await props.params;
	return (
		<div className="h-full w-full overflow-hidden">
			<NowingSplitCanvas workspaceId={workspace_id} hasActiveThread={false} />
		</div>
	);
}
