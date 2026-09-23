import type React from "react";
import { use } from "react";
import { PlaygroundLayoutShell } from "../../playground/layout-shell";

export default function PlaygroundSettingsLayout({
	params,
	children,
}: {
	params: Promise<{ workspace_id: string }>;
	children: React.ReactNode;
}) {
	const { workspace_id } = use(params);

	return (
		<div className="mx-auto w-full max-w-6xl">
			<PlaygroundLayoutShell workspaceId={workspace_id}>{children}</PlaygroundLayoutShell>
		</div>
	);
}
