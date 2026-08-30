"use client";

import { AlertCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import type { FC } from "react";
import { Button } from "@/components/ui/button";

export const ChatUnavailableNotice: FC<{ workspaceId: number; canConfigure: boolean }> = ({
	workspaceId,
	canConfigure,
}) => {
	const router = useRouter();

	return (
		<div className="relative z-0 -mb-5 flex min-w-0 items-center gap-2 rounded-t-3xl bg-popover px-4 pt-2 pb-6 shadow-sm shadow-black/5 dark:shadow-black/10">
			<div className="flex min-w-0 items-center gap-2 text-[13px] font-normal text-muted-foreground select-none">
				<AlertCircle className="size-4 shrink-0" aria-hidden="true" />
				<span className="truncate">
					{canConfigure
						? "Connect a chat model to start chatting."
						: "No model available. Ask a workspace admin to connect a chat model."}
				</span>
			</div>
			<div className="min-w-0 flex-1" />
			{canConfigure ? (
				<Button
					type="button"
					size="sm"
					className="h-6 shrink-0 cursor-pointer gap-2 rounded-md px-2.5 text-xs font-medium select-none"
					onClick={() => router.push(`/dashboard/${workspaceId}/workspace-settings/models`)}
				>
					<span className="sm:hidden">Connect</span>
					<span className="hidden sm:inline">Connect a model</span>
				</Button>
			) : null}
		</div>
	);
};
