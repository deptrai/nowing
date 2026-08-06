import { PlaybooksContent } from "./playbooks-content";

export default async function PlaybooksPage({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await params;

	return (
		<div className="mx-auto w-full max-w-5xl space-y-6">
			<PlaybooksContent workspaceId={Number(workspace_id)} />
		</div>
	);
}
