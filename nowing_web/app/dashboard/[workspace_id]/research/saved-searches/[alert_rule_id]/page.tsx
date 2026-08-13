import { SavedSearchDetailContent } from "./saved-search-detail-content";

export default async function SavedSearchDetailPage({
	params,
}: {
	params: Promise<{ workspace_id: string; alert_rule_id: string }>;
}) {
	const { workspace_id, alert_rule_id } = await params;

	return (
		<div className="w-full space-y-6">
			<SavedSearchDetailContent workspaceId={Number(workspace_id)} alertRuleId={alert_rule_id} />
		</div>
	);
}
