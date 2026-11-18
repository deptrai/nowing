import { CampaignDetail } from "@/components/leads/campaigns/CampaignDetail";

export const dynamic = "force-dynamic";

export default async function LeadCampaignDetailPage(props: {
	params: Promise<{ workspace_id: string; campaign_id: string }>;
}) {
	const { workspace_id, campaign_id } = await props.params;

	return (
		<div className="flex-1 flex flex-col p-6 space-y-4 max-w-full overflow-y-auto">
			<CampaignDetail workspaceId={workspace_id} campaignId={campaign_id} />
		</div>
	);
}
