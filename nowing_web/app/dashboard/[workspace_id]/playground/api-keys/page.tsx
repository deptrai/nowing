import { Info } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { WorkspaceApiAccessControl } from "@/components/settings/workspace-api-access-control";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { ApiKeyContent } from "../../user-settings/components/ApiKeyContent";

export default async function PlaygroundApiKeysPage({
	params,
}: {
	params: Promise<{ workspace_id: string }>;
}) {
	const t = await getTranslations("playground");
	const { workspace_id } = await params;
	const workspaceId = Number(workspace_id);

	return (
		<div className="mx-auto w-full max-w-5xl space-y-6">
			<div className="space-y-1">
				<h2 className="font-serif text-2xl sm:text-3xl font-normal tracking-tight">
					{t("api_keys_title")}
				</h2>
				<p className="text-xs sm:text-sm text-muted-foreground font-sans">{t("api_keys_desc")}</p>
			</div>

			<Alert>
				<Info />
				<AlertDescription>{t("api_keys_alert")}</AlertDescription>
			</Alert>

			<section>
				<WorkspaceApiAccessControl workspaceId={workspaceId} />
			</section>

			<Separator className="bg-border" />

			<section>
				<ApiKeyContent />
			</section>
		</div>
	);
}
