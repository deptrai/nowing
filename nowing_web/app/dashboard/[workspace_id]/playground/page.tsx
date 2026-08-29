import type { Metadata } from "next";
import { PlaygroundIndex } from "./components/playground-index";

export const metadata: Metadata = {
	title: "Playground",
};

export default async function PlaygroundPage({
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
