"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useSetAtom } from "jotai";
import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { setCurrentThreadMetadataAtom } from "@/atoms/chat/current-thread.atom";
import { syncChatTabAtom } from "@/atoms/tabs/tabs.atom";
import { prefetchThreadData } from "./use-thread-queries";

interface ActivateChatThreadInput {
	id: number | null;
	workspaceId: number | string;
	navigate?: boolean;
}

export function getWorkspaceId(workspaceId: number | string): number {
	const parsed = typeof workspaceId === "number" ? workspaceId : Number.parseInt(workspaceId, 10);
	return Number.isNaN(parsed) ? 0 : parsed;
}

export function getChatUrl(workspaceId: number | string, threadId: number | null): string {
	return threadId
		? `/dashboard/${workspaceId}/new-chat/${threadId}`
		: `/dashboard/${workspaceId}/new-chat`;
}

export function useActivateChatThread() {
	const router = useRouter();
	const queryClient = useQueryClient();
	const syncChatTab = useSetAtom(syncChatTabAtom);
	const setCurrentThreadMetadata = useSetAtom(setCurrentThreadMetadataAtom);

	const prefetchChatThread = useCallback(
		(threadId: number | null | undefined) => {
			if (typeof threadId === "number" && threadId > 0) {
				prefetchThreadData(queryClient, threadId);
			}
		},
		[queryClient]
	);

	const activateChatThread = useCallback(
		({ id, workspaceId, navigate = true }: ActivateChatThreadInput) => {
			const numericWorkspaceId = getWorkspaceId(workspaceId);
			const chatUrl = getChatUrl(workspaceId, id);

			syncChatTab({
				chatId: id,
				workspaceId: numericWorkspaceId,
			});

			setCurrentThreadMetadata({
				id,
				workspaceId: numericWorkspaceId,
			});

			if (id) {
				prefetchThreadData(queryClient, id);
			}

			if (navigate) {
				router.push(chatUrl);
			}
		},
		[queryClient, router, setCurrentThreadMetadata, syncChatTab]
	);

	return { activateChatThread, prefetchChatThread };
}
