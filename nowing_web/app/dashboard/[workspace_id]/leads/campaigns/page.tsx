import { CampaignList } from "@/components/leads/campaigns/CampaignList";

export const dynamic = "force-dynamic";

export default async function LeadCampaignsPage(props: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await props.params;

	return (
		<div className="flex-1 flex flex-col p-6 space-y-4 max-w-full overflow-y-auto">
			<CampaignList workspaceId={workspace_id} />
		</div>
	);
}
