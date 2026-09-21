"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAnonymousMode } from "@/contexts/anonymous-mode";
import { useLoginGate } from "@/contexts/login-gate";
import { useAnnouncements } from "@/hooks/use-announcements";
import { anonymousChatApiService } from "@/lib/apis/anonymous-chat-api.service";
import type { ChatItem, PageUsage, Workspace } from "../types/layout.types";
import { LayoutShell } from "../ui/shell";

interface FreeLayoutDataProviderProps {
	children: ReactNode;
}

export function FreeLayoutDataProvider({ children }: FreeLayoutDataProviderProps) {
	const t = useTranslations("layout");
	const router = useRouter();
	const { gate } = useLoginGate();
	const anonMode = useAnonymousMode();
	const { unreadCount: announcementUnreadCount } = useAnnouncements();
	const [quota, setQuota] = useState<{ used: number; limit: number } | null>(null);

	const GUEST_SPACE: Workspace = useMemo(
		() => ({
			id: 0,
			name: t("free_workspace_name"),
			description: t("free_workspace_desc"),
			isOwner: false,
			memberCount: 1,
		}),
		[t]
	);

	useEffect(() => {
		anonymousChatApiService
			.getQuota()
			.then((q) => {
				setQuota({ used: q.used, limit: q.limit });
			})
			.catch(() => {});
	}, []);

	const resetChat = useCallback(() => {
		if (anonMode.isAnonymous) {
			anonMode.resetChat();
		}
	}, [anonMode]);

	const gatedAction = useCallback((feature: string) => () => gate(feature), [gate]);

	const pageUsage: PageUsage | undefined = quota
		? { pagesUsed: quota.used, pagesLimit: quota.limit }
		: undefined;

	const handleChatSelect = useCallback((_chat: ChatItem) => gate(t("view_chat_history")), [gate]);

	const handleAnnouncements = useCallback(() => gate("see what's new"), [gate]);

	const handleWorkspaceSelect = useCallback((_id: number) => gate(t("switch_workspaces")), [gate]);

	return (
		<LayoutShell
			workspaces={[GUEST_SPACE]}
			activeWorkspaceId={0}
			onWorkspaceSelect={handleWorkspaceSelect}
			onWorkspaceSettings={gatedAction(t("workspace_settings"))}
			onAddWorkspace={gatedAction(t("create_workspaces"))}
			workspace={GUEST_SPACE}
			navItems={[]}
			chats={[]}
			activeChatId={null}
			onNewChat={resetChat}
			onChatSelect={handleChatSelect}
			onChatRename={gatedAction(t("rename_chats"))}
			onChatDelete={gatedAction(t("delete_chats"))}
			onChatArchive={gatedAction(t("archive_chats"))}
			onViewAllChats={gatedAction(t("view_chat_history"))}
			user={{
				email: t("guest_user"),
				name: t("guest_user"),
			}}
			onSettings={gatedAction(t("workspace_settings"))}
			onManageMembers={gatedAction(t("team_management"))}
			onUserSettings={gatedAction(t("account_settings"))}
			onAnnouncements={handleAnnouncements}
			announcementUnreadCount={announcementUnreadCount}
			onLogout={() => router.push("/register")}
			pageUsage={pageUsage}
			isChatPage
			isLoadingChats={false}
		>
			{children}
		</LayoutShell>
	);
}
