import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { PlaygroundIndex } from "./components/playground-index";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("playground");
	return {
		title: t("playground"),
	};
}

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
