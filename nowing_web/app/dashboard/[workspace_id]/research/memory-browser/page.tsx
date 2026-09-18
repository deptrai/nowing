import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { MemoryBrowserPageContent } from "./memory-browser-page-content";

export async function generateMetadata(): Promise<Metadata> {
	const t = await getTranslations("MemoryBrowser");
	return {
		title: t("page_title"),
	};
}

export default async function MemoryBrowserPage({
  params,
}: {
  params: Promise<{ workspace_id: string }>;
}) {
  const { workspace_id } = await params;
  return (
    <div className="w-full space-y-6">
      <MemoryBrowserPageContent workspaceId={Number(workspace_id)} />
    </div>
  );
}
