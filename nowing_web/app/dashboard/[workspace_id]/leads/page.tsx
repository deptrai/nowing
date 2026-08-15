import { OrigamiSplitCanvas } from "@/components/leads/OrigamiSplitCanvas";

export default async function LeadsPage(props: { params: Promise<{ workspace_id: string }> }) {
	const { workspace_id } = await props.params;

	return (
		<div className="w-full h-full p-2 md:p-4">
			<OrigamiSplitCanvas workspaceId={workspace_id} />
		</div>
	);
}
