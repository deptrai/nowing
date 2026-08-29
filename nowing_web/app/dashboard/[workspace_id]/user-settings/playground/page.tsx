import type { Metadata } from "next";
import { PlaygroundIndex } from "../../playground/components/playground-index";


export const metadata: Metadata = {
	title: "API Playground",
};

export default async function PlaygroundSettingsPage({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const { workspace_id } = await params;

	return (
		<div className="mx-auto w-full max-w-5xl">
			<PlaygroundIndex workspaceId={Number(workspace_id)} />
		</div>
	);
}
