import type { Metadata } from "next";
import { MemoryBrowserPageContent } from "./memory-browser-page-content";

export const metadata: Metadata = {
  title: "Memory Browser",
};

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
