import { CampaignBuilder } from "@/components/leads/campaign-builder/CampaignBuilder";

export const dynamic = "force-dynamic";

export default async function NewLeadCampaignPage(props: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await props.params;

	return (
		<div className="flex-1 flex flex-col p-6 space-y-4 max-w-full overflow-y-auto">
			<CampaignBuilder workspaceId={workspace_id} />
		</div>
	);
}
